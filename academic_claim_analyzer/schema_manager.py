# academic_claim_analyzer/schema_manager.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Type
import logging

logger = logging.getLogger(__name__)

def create_model_from_schema(model_name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model from a dictionary schema.
    
    Args:
        model_name: The name for the created model
        schema: Dictionary containing field definitions with type and description
        
    Returns:
        A dynamically created Pydantic model class
    """
    annotations = {}
    fields = {}
    properties = {}

    for field_name, field_info in schema.items():
        field_type = field_info.get('type', 'string').lower()
        description = field_info.get('description', '')

        if field_type == 'number':
            python_type = float
            description += " (Use -1.0 if unknown)"
            default_value = -1.0
            json_type = 'number'
        elif field_type == 'integer':
            python_type = int
            description += " (Use -1 if unknown)"
            default_value = -1
            json_type = 'integer'
        elif field_type == 'boolean':
            python_type = bool
            description += " (Must be true/false)"
            default_value = False
            json_type = 'boolean'
        elif field_type in ['array', 'list']:
            from typing import List as PyList
            python_type = PyList[str]
            description += " (List of strings, empty if none)"
            default_value = []
            json_type = 'array'
            properties[field_name] = {
                'type': 'array',
                'description': description,
                'items': {'type': 'string'}
            }
            annotations[field_name] = python_type
            fields[field_name] = Field(default=default_value, description=description)
            continue
        else:
            python_type = str
            description += " (String, use 'N/A' if unknown)"
            default_value = "N/A"
            json_type = 'string'

        annotations[field_name] = python_type
        fields[field_name] = Field(default=default_value, description=description)
        if field_name not in properties:
            properties[field_name] = {
                'type': json_type,
                'description': description
            }

    namespace = {
        '__annotations__': annotations,
        **fields,
        'model_config': {
            'json_schema_extra': {
                'type': 'object',
                'required': list(annotations.keys()),
                'additionalProperties': False,
                'properties': properties
            }
        }
    }

    return type(model_name, (BaseModel,), namespace)

def create_combined_schema(
    exclusion_schema: Optional[Type[BaseModel]],
    extraction_schema: Optional[Type[BaseModel]]
) -> Type[BaseModel]:
    """
    Creates a combined schema from exclusion and extraction schemas
    
    Args:
        exclusion_schema: Pydantic model for exclusion criteria
        extraction_schema: Pydantic model for data extraction
        
    Returns:
        A combined Pydantic model with fields from both schemas
    """
    from pydantic import Field

    fields = {}
    annotations = {}
    properties = {}

    if exclusion_schema:
        for name, field in exclusion_schema.model_fields.items():
            annotations[name] = field.annotation
            fields[name] = Field(description=field.description or f"Exclusion: {name}")
            properties[name] = {
                'type': 'boolean',
                'description': field.description or f"Exclusion: {name}"
            }

    if extraction_schema:
        for name, field in extraction_schema.model_fields.items():
            annotations[name] = field.annotation
            fields[name] = Field(description=field.description or f"Extraction: {name}")
            if field.annotation == int:
                json_type = 'integer'
            elif field.annotation == float:
                json_type = 'number'
            elif field.annotation == bool:
                json_type = 'boolean'
            else:
                json_type = 'string'
            properties[name] = {
                'type': json_type,
                'description': field.description or f"Extraction: {name}"
            }

    namespace = {
        '__annotations__': annotations,
        **fields,
        'model_config': {
            'json_schema_extra': {
                'type': 'object',
                'required': list(annotations.keys()),
                'additionalProperties': False,
                'properties': properties
            }
        }
    }

    return type("CombinedSchema", (BaseModel,), namespace)