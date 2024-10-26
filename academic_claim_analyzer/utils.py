# academic_claim_analyzer/utils.py

from pydantic import create_model, Field, BaseModel
from typing import Any, Dict, List, Type, Union
import logging

logger = logging.getLogger(__name__)

def normalize_field_info(field_info: Union[Dict[str, Any], List[Any], str]) -> Dict[str, Any]:
    """Normalize field information into a consistent dictionary format."""
    if isinstance(field_info, dict):
        return field_info
    elif isinstance(field_info, list):
        # If it's a list, treat it as a list type with the first item as the element type
        return {
            'type': 'list',
            'description': '',
            'items': field_info[0] if field_info else {'type': 'str'}
        }
    elif isinstance(field_info, str):
        return {
            'type': field_info,
            'description': ''
        }
    else:
        return {
            'type': 'str',
            'description': ''
        }

def create_pydantic_model_from_schema(model_name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model from a dictionary schema.
    Handles various schema formats and normalizes them.
    """
    fields = {}
    type_mapping = {
        'string': str,
        'str': str,
        'integer': int,
        'int': int,
        'float': float,
        'boolean': bool,
        'bool': bool,
        'list': List[Any],
        'dict': Dict[str, Any],
        'any': Any
    }

    for field_name, field_info in schema.items():
        try:
            # Normalize the field information
            normalized_info = normalize_field_info(field_info)
            
            # Get the field type
            field_type = normalized_info.get('type', 'str').lower()
            field_description = normalized_info.get('description', '')

            # Handle list types with specific item types
            if field_type == 'list' and 'items' in normalized_info:
                item_info = normalize_field_info(normalized_info['items'])
                item_type = type_mapping.get(item_info.get('type', 'str').lower(), Any)
                python_type = List[item_type]
            else:
                python_type = type_mapping.get(field_type, str)

            fields[field_name] = (python_type, Field(description=field_description))
            
        except Exception as e:
            logger.warning(f"Error processing field '{field_name}': {str(e)}. Using string type as fallback.")
            fields[field_name] = (str, Field(description="Fallback field due to processing error"))

    try:
        model = create_model(model_name, **fields)
        return model
    except Exception as e:
        logger.error(f"Failed to create Pydantic model: {str(e)}")
        raise