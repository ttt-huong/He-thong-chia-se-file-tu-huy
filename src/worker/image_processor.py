"""
Image Processor - Xử lý ảnh (compress, thumbnail)
Chương 2: Image Processing với Pillow
"""

import os
import logging
from PIL import Image
from typing import Tuple, Optional

from src.config.settings import THUMBNAIL_SIZE

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Image processing functions
    - Compression (reduce file size)
    - Thumbnail generation
    - Dominant color extraction
    - Image metadata (dimensions)
    - Future: Watermark, resize, format conversion, etc.
    """
    
    @staticmethod
    def dominant_color_hex(image_path: str) -> Optional[str]:
        """
        Extract dominant color from image (1x1 average)
        Returns hex color code like '#FF5733'
        """
        try:
            if not os.path.exists(image_path):
                return None
            
            img = Image.open(image_path)
            img = img.convert('RGB').resize((1, 1), resample=Image.Resampling.BICUBIC)
            r, g, b = img.getpixel((0, 0))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception as e:
            logger.error(f"Error extracting dominant color: {e}")
            return None
    
    @staticmethod
    def get_image_info(image_path: str) -> Optional[dict]:
        """
        Get basic image metadata (dimensions, format, mode)
        """
        try:
            if not os.path.exists(image_path):
                return None
            
            img = Image.open(image_path)
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode
            }
        except Exception as e:
            logger.error(f"Error reading image info: {e}")
            return None
    
    @staticmethod
    def compress_image(
        input_path: str,
        output_path: Optional[str] = None,
        quality: int = 85,
        max_dimension: Optional[int] = None
    ) -> Tuple[bool, str, dict]:
        """
        Compress image to reduce file size
        
        Args:
            input_path: Path to original image
            output_path: Path to save compressed image (default: overwrite original)
            quality: JPEG quality (1-100, default: 85)
            max_dimension: Maximum width/height (maintains aspect ratio)
        
        Returns:
            Tuple of (success, output_path, metadata)
        """
        try:
            if not os.path.exists(input_path):
                logger.error(f"Input file not found: {input_path}")
                return False, "", {"error": "Input file not found"}
            
            # Open image
            img = Image.open(input_path)
            original_format = img.format
            original_mode = img.mode
            original_size = os.path.getsize(input_path)
            original_dimensions = img.size
            
            logger.info(f"Compressing image: {input_path} "
                       f"({original_dimensions[0]}x{original_dimensions[1]}, "
                       f"{original_size / 1024:.2f} KB)")
            
            # Convert RGBA to RGB if saving as JPEG
            if original_mode == 'RGBA' and (output_path and output_path.lower().endswith('.jpg')):
                # Create white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = rgb_img
            elif original_mode == 'RGBA':
                # Keep RGBA but convert to RGB if format doesn't support transparency
                if original_format in ['JPEG', 'JPG']:
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])
                    img = rgb_img
            
            # Resize if max_dimension specified
            if max_dimension and max(img.size) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                logger.info(f"Resized to: {img.size[0]}x{img.size[1]}")
            
            # Determine output path
            if not output_path:
                output_path = input_path
            
            # Save compressed image
            save_kwargs = {
                'optimize': True,
                'quality': quality
            }
            
            # Format-specific options
            if original_format in ['JPEG', 'JPG'] or output_path.lower().endswith(('.jpg', '.jpeg')):
                save_kwargs['format'] = 'JPEG'
                save_kwargs['progressive'] = True  # Progressive JPEG
            elif original_format == 'PNG' or output_path.lower().endswith('.png'):
                save_kwargs['format'] = 'PNG'
                save_kwargs['compress_level'] = 9  # Max PNG compression
            elif original_format == 'WEBP' or output_path.lower().endswith('.webp'):
                save_kwargs['format'] = 'WEBP'
                save_kwargs['quality'] = quality
            else:
                save_kwargs['format'] = original_format
            
            img.save(output_path, **save_kwargs)
            
            # Get compressed size
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            metadata = {
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': round(compression_ratio, 2),
                'original_dimensions': original_dimensions,
                'final_dimensions': img.size,
                'quality': quality
            }
            
            logger.info(f"Compression successful: {original_size / 1024:.2f} KB → "
                       f"{compressed_size / 1024:.2f} KB ({compression_ratio:.1f}% reduction)")
            
            return True, output_path, metadata
        
        except Exception as e:
            logger.error(f"Error compressing image: {e}", exc_info=True)
            return False, "", {"error": str(e)}
    
    @staticmethod
    def create_thumbnail(
        input_path: str,
        output_path: Optional[str] = None,
        size: Tuple[int, int] = THUMBNAIL_SIZE,
        quality: int = 85
    ) -> Tuple[bool, str, dict]:
        """
        Create thumbnail from image
        
        Args:
            input_path: Path to original image
            output_path: Path to save thumbnail (default: input_path with _thumb suffix)
            size: Thumbnail size (width, height)
            quality: JPEG quality
        
        Returns:
            Tuple of (success, output_path, metadata)
        """
        try:
            if not os.path.exists(input_path):
                logger.error(f"Input file not found: {input_path}")
                return False, "", {"error": "Input file not found"}
            
            # Open image
            img = Image.open(input_path)
            original_size = img.size
            
            logger.info(f"Creating thumbnail: {input_path} ({original_size[0]}x{original_size[1]}) "
                       f"→ {size[0]}x{size[1]}")
            
            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img
            
            # Create thumbnail (maintains aspect ratio)
            img_copy = img.copy()
            img_copy.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Determine output path
            if not output_path:
                base, ext = os.path.splitext(input_path)
                output_path = f"{base}_thumb{ext}"
            
            # Save thumbnail
            save_kwargs = {
                'optimize': True,
                'quality': quality
            }
            
            if output_path.lower().endswith(('.jpg', '.jpeg')):
                save_kwargs['format'] = 'JPEG'
            elif output_path.lower().endswith('.png'):
                save_kwargs['format'] = 'PNG'
            elif output_path.lower().endswith('.webp'):
                save_kwargs['format'] = 'WEBP'
            
            img_copy.save(output_path, **save_kwargs)
            
            # Get thumbnail size
            thumb_size = os.path.getsize(output_path)
            
            metadata = {
                'original_dimensions': original_size,
                'thumbnail_dimensions': img_copy.size,
                'thumbnail_size': thumb_size,
                'quality': quality
            }
            
            logger.info(f"Thumbnail created: {output_path} "
                       f"({img_copy.size[0]}x{img_copy.size[1]}, {thumb_size / 1024:.2f} KB)")
            
            return True, output_path, metadata
        
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}", exc_info=True)
            return False, "", {"error": str(e)}
    
    @staticmethod
    def get_image_info(input_path: str) -> Optional[dict]:
        """
        Get image metadata
        
        Args:
            input_path: Path to image
        
        Returns:
            Dict with image info or None
        """
        try:
            if not os.path.exists(input_path):
                return None
            
            img = Image.open(input_path)
            file_size = os.path.getsize(input_path)
            
            info = {
                'format': img.format,
                'mode': img.mode,
                'dimensions': img.size,
                'width': img.size[0],
                'height': img.size[1],
                'file_size': file_size,
                'file_size_kb': round(file_size / 1024, 2)
            }
            
            # EXIF data if available
            if hasattr(img, '_getexif') and img._getexif():
                info['has_exif'] = True
            
            return info
        
        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return None
    
    @staticmethod
    def is_valid_image(file_path: str) -> bool:
        """
        Check if file is a valid image
        
        Args:
            file_path: Path to file
        
        Returns:
            True if valid image, False otherwise
        """
        try:
            img = Image.open(file_path)
            img.verify()  # Verify it's a valid image
            return True
        except Exception:
            return False

    @staticmethod
    def dominant_color_hex(input_path: str) -> Optional[str]:
        """
        Compute a simple dominant/average color and return as hex string.
        Fast approach: resize to small thumbnail and average pixels.
        """
        try:
            if not os.path.exists(input_path):
                return None
            img = Image.open(input_path).convert('RGB')
            # Downscale to reduce computation
            img.thumbnail((50, 50), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            if not pixels:
                return None
            r = sum(p[0] for p in pixels) // len(pixels)
            g = sum(p[1] for p in pixels) // len(pixels)
            b = sum(p[2] for p in pixels) // len(pixels)
            return '#%02x%02x%02x' % (r, g, b)
        except Exception:
            return None
