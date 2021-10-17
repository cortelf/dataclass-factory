from enum import Enum
from typing import Callable, cast, Dict, Generic, List, Optional, Sequence, Tuple, Union

from .common import InnerConverter, Parser, ParserGetter, Serializer, SerializerGetter, T
from .naming import NameStyle
from .path_utils import NameMapping
from .validators import prepare_validators

FieldMapper = Callable[[str], Tuple[str, bool]]
SimpleFieldMapping = Dict[str, str]


class Unknown(Enum):
    SKIP = 'skip'
    FORBID = 'forbid'
    STORE = 'include'


RuleForUnknown = Union[Unknown, str, Sequence[str], None]


class Schema(Generic[T]):
    pre_validators: Dict[Optional[str], List[Parser]]
    post_validators: Dict[Optional[str], List[Parser]]

    def __init__(  # noqa C901,CCR001
        self,
        only: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        name_mapping: NameMapping = None,
        only_mapped: Optional[bool] = None,

        name_style: Optional[NameStyle] = None,
        trim_trailing_underscore: Optional[bool] = None,
        skip_internal: Optional[bool] = None,

        serializer: Optional[Serializer[T]] = None,
        get_serializer: Optional[SerializerGetter[T]] = None,

        parser: Optional[Parser[T]] = None,
        get_parser: Optional[ParserGetter[T]] = None,

        pre_parse: Optional[Callable] = None,
        post_parse: Optional[InnerConverter[T]] = None,
        pre_serialize: Optional[InnerConverter[T]] = None,
        post_serialize: Optional[Callable] = None,

        omit_default: Optional[bool] = None,
        unknown: RuleForUnknown = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.pre_validators, self.post_validators = prepare_validators(self)
        if only is not None or not hasattr(self, "only"):
            self.only = only
        if exclude is not None or not hasattr(self, "exclude"):
            self.exclude = exclude
        if name_mapping is not None or not hasattr(self, "name_mapping"):
            self.name_mapping = name_mapping
        if only_mapped is not None or not hasattr(self, "only_mapped"):
            self.only_mapped = only_mapped

        if name_style is not None or not hasattr(self, "name_style"):
            self.name_style = name_style
        if trim_trailing_underscore is not None or not hasattr(self, "trim_trailing_underscore"):
            self.trim_trailing_underscore = trim_trailing_underscore
        if skip_internal is not None or not hasattr(self, "skip_internal"):
            self.skip_internal = skip_internal

        if serializer is not None or not hasattr(self, "serializer"):
            self.serializer = serializer
        if get_serializer is not None or not hasattr(self, "get_serializer"):
            self.get_serializer = get_serializer

        if parser is not None or not hasattr(self, "parser"):
            self.parser = parser
        if get_parser is not None or not hasattr(self, "get_parser"):
            self.get_parser = get_parser

        if pre_parse is not None or not hasattr(self, "pre_parse"):
            self.pre_parse = pre_parse
        if post_parse is not None or not hasattr(self, "post_parse"):
            self.post_parse = post_parse
        if pre_serialize is not None or not hasattr(self, "pre_serialize"):
            self.pre_serialize = pre_serialize
        if post_serialize is not None or not hasattr(self, "post_serialize"):
            self.post_serialize = post_serialize

        if omit_default is not None or not hasattr(self, "omit_default"):
            self.omit_default = omit_default
        if unknown is not None or not hasattr(self, "unknown"):
            self.unknown = unknown

        if name is not None or not hasattr(self, "name"):
            self.name = name
        if description is not None or not hasattr(self, "description"):
            self.description = description


SCHEMA_FIELDS = {
    "only",
    "exclude",
    "name_mapping",
    "only_mapped",
    "name_style",
    "trim_trailing_underscore",
    "skip_internal",
    "serializer",
    "get_serializer",
    "parser",
    "get_parser",
    "pre_parse",
    "post_parse",
    "pre_serialize",
    "post_serialize",
    "omit_default",
    "unknown",
    "name",
    "description",
    "pre_validators",
    "post_validators",
}


class SchemaProxy:
    def __init__(self, *schemas: Schema):
        # the first empty schema accumulates changes that do not touch actual schema
        acc_schema = Schema()
        # ignore this fields at search in __getattr__
        acc_schema.pre_validators = None  # type: ignore
        acc_schema.post_validators = None  # type: ignore
        self._schemas = [acc_schema, *schemas]

    def __getattr__(self, item):
        for schema in self._schemas:
            res = getattr(schema, item, None)
            if res is not None:
                return res

        if item in SCHEMA_FIELDS:
            return None

        raise AttributeError(f"Field `{item}` is not defined for Schema")

    def __setattr__(self, key, value):
        if key == "_schemas":
            return super().__setattr__(key, value)
        return setattr(self._schemas[0], key, value)

    def __getstate__(self):
        return self._schemas

    def __setstate__(self, state):
        self._schemas = state


def merge_schema(*schemas: Optional[Schema]) -> Schema:
    return cast(Schema, SchemaProxy(*[s for s in schemas if s]))
