"""
Patch SQLAlchemy 2.0.x + Python 3.13 compatibility issue
Chạy trước khi import SQLAlchemy
"""

import sys
import typing

if sys.version_info >= (3, 13):
    # Fix TypingOnly assertion error
    original_init_subclass = typing._TypingBase.__init_subclass__ if hasattr(typing, '_TypingBase') else None
    
    def patched_init_subclass(cls, **kwargs):
        # Remove extra attributes that cause assertion error
        for attr in ['__firstlineno__', '__static_attributes__']:
            if hasattr(cls, attr):
                try:
                    delattr(cls, attr)
                except (AttributeError, TypeError):
                    pass
        if original_init_subclass:
            return original_init_subclass(**kwargs)
    
    # Monkey-patch SQLAlchemy's TypingOnly class
    try:
        from sqlalchemy import sql
        from sqlalchemy.sql import elements
        
        if hasattr(elements, 'SQLCoreOperations'):
            # Clean up problematic attributes before SQLAlchemy initialization
            for attr in ['__firstlineno__', '__static_attributes__']:
                try:
                    if hasattr(elements.SQLCoreOperations, attr):
                        delattr(elements.SQLCoreOperations, attr)
                except (AttributeError, TypeError):
                    pass
    except Exception as e:
        print(f"Warning: Could not patch SQLAlchemy: {e}")
