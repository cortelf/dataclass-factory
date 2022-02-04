import inspect
from abc import abstractmethod, ABC
from dataclasses import fields as dc_fields, is_dataclass, MISSING as DC_MISSING, Field as DCField, replace
from inspect import Signature, Parameter
from types import MappingProxyType
from typing import Any, get_type_hints, final, Dict, Iterable, Callable, Tuple

from .definitions import DefaultValue, DefaultFactory, Default, NoDefault
from .essential import Mediator, CannotProvide
from .fields_basics import (
    InputFieldsFigure, OutputFieldsFigure,
    InputFFRequest, OutputFFRequest,
    GetterKind, ExtraKwargs
)
from .request_cls import FieldRM, InputFieldRM, ParamKind
from .static_provider import StaticProvider, static_provision_action
from ..type_tools import is_typed_dict_class, is_named_tuple_class

_PARAM_KIND_CONV: Dict[Any, ParamKind] = {
    Parameter.POSITIONAL_ONLY: ParamKind.POS_ONLY,
    Parameter.POSITIONAL_OR_KEYWORD: ParamKind.POS_OR_KW,
    Parameter.KEYWORD_ONLY: ParamKind.KW_ONLY,
}


def get_func_iff(func, params_slice=slice(0, None)) -> InputFieldsFigure:
    params = list(
        inspect.signature(func).parameters.values()
    )[params_slice]

    return signature_params_to_iff(func, params)


def _is_empty(value):
    return value is Signature.empty


def signature_params_to_iff(constructor: Callable, params: Iterable[Parameter]) -> InputFieldsFigure:
    kinds = [p.kind for p in params]

    if Parameter.VAR_POSITIONAL in kinds:
        raise ValueError(
            f'Can not create InputFieldsFigure'
            f' from the function that has {Parameter.VAR_POSITIONAL}'
            f' parameter'
        )

    extra = (
        ExtraKwargs()
        if Parameter.VAR_KEYWORD in kinds else
        None
    )

    return InputFieldsFigure(
        constructor=constructor,
        fields=tuple(
            InputFieldRM(
                type=Any if _is_empty(param.annotation) else param.annotation,
                field_name=param.name,
                is_required=_is_empty(param.default),
                default=NoDefault() if _is_empty(param.default) else DefaultValue(param.default),
                metadata=MappingProxyType({}),
                param_kind=_PARAM_KIND_CONV[param.kind],
            )
            for param in params
            if param.kind != Parameter.VAR_KEYWORD
        ),
        extra=extra,
    )


class TypeOnlyInputFFProvider(StaticProvider, ABC):
    # noinspection PyUnusedLocal
    @final
    @static_provision_action(InputFFRequest)
    def _provide_input_fields_figure(self, mediator: Mediator, request: InputFFRequest) -> InputFieldsFigure:
        return self._get_input_fields_figure(request.type)

    @abstractmethod
    def _get_input_fields_figure(self, tp) -> InputFieldsFigure:
        pass


class TypeOnlyOutputFFProvider(StaticProvider, ABC):
    # noinspection PyUnusedLocal
    @final
    @static_provision_action(OutputFFRequest)
    def _provide_output_fields_figure(self, mediator: Mediator, request: OutputFFRequest) -> OutputFieldsFigure:
        return self._get_output_fields_figure(request.type)

    @abstractmethod
    def _get_output_fields_figure(self, tp) -> OutputFieldsFigure:
        pass


class NamedTupleFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    def _get_input_fields_figure(self, tp) -> InputFieldsFigure:
        if not is_named_tuple_class(tp):
            raise CannotProvide

        iff = get_func_iff(tp.__new__, slice(1, None))

        type_hints = get_type_hints(tp)

        # At <3.9 namedtuple does not generate typehints at __new__
        return InputFieldsFigure(
            constructor=tp,
            extra=iff.extra,
            fields=tuple(
                replace(
                    fld,
                    type=type_hints.get(fld.field_name, Any)
                )
                for fld in iff.fields
            )
        )

    def _get_output_fields_figure(self, tp) -> OutputFieldsFigure:
        return OutputFieldsFigure(
            fields=tuple(
                FieldRM(
                    field_name=fld.field_name,
                    type=fld.type,
                    default=fld.default,
                    is_required=True,
                    metadata=fld.metadata,
                )
                for fld in self._get_input_fields_figure(tp).fields
            ),
            getter_kind=GetterKind.ATTR,
        )


def _to_inp(param_kind: ParamKind, fields: Iterable[FieldRM]) -> Tuple[InputFieldRM, ...]:
    return tuple(
        InputFieldRM(
            field_name=f.field_name,
            type=f.type,
            default=f.default,
            is_required=f.is_required,
            metadata=f.metadata,
            param_kind=param_kind,
        )
        for f in fields
    )


class TypedDictFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    def _get_fields(self, tp):
        if not is_typed_dict_class(tp):
            raise CannotProvide

        is_required = tp.__total__

        return tuple(
            FieldRM(
                type=tp,
                field_name=name,
                default=NoDefault(),
                is_required=is_required,
                metadata=MappingProxyType({}),
            )
            for name, tp in get_type_hints(tp).items()
        )

    def _get_input_fields_figure(self, tp):
        return InputFieldsFigure(
            constructor=tp,
            fields=_to_inp(ParamKind.KW_ONLY, self._get_fields(tp)),
            extra=None,
        )

    def _get_output_fields_figure(self, tp):
        return OutputFieldsFigure(
            fields=self._get_fields(tp),
            getter_kind=GetterKind.ITEM,
        )


def get_dc_default(field: DCField) -> Default:
    if field.default is not DC_MISSING:
        return DefaultValue(field.default)
    if field.default_factory is not DC_MISSING:
        return DefaultFactory(field.default_factory)
    return NoDefault()


def _dc_field_to_field_rm(fld: DCField, required_det: Callable[[Default], bool]):
    default = get_dc_default(fld)

    return FieldRM(
        type=fld.type,
        field_name=fld.name,
        default=default,
        is_required=required_det(default),
        metadata=fld.metadata,
    )


def all_dc_fields(cls) -> Dict[str, DCField]:
    """Builtin introspection function hides
    some fields like InitVar or ClassVar.
    That function return full dict
    """
    return cls.__dataclass_fields__


class DataclassFieldsProvider(TypeOnlyInputFFProvider, TypeOnlyOutputFFProvider):
    """This provider does not work properly if __init__ signature differs from
    that would be created by dataclass decorator.

    It happens because we can not distinguish __init__ that generated
    by @dataclass and __init__ that created by other ways.
    And we can not analyze only __init__ signature
    because @dataclass uses private constant
    as default value for fields with default_factory
    """

    def _get_input_fields_figure(self, tp):
        if not is_dataclass(tp):
            raise CannotProvide

        name_to_dc_field = all_dc_fields(tp)

        init_params = list(
            inspect.signature(tp.__init__).parameters.keys()
        )[1:]

        return InputFieldsFigure(
            constructor=tp,
            fields=_to_inp(
                ParamKind.POS_OR_KW,
                [
                    _dc_field_to_field_rm(
                        name_to_dc_field[field_name],
                        lambda default: default == NoDefault()
                    )
                    for field_name in init_params
                ]
            ),
            extra=None,
        )

    def _get_output_fields_figure(self, tp):
        if not is_dataclass(tp):
            raise CannotProvide

        return OutputFieldsFigure(
            fields=tuple(
                _dc_field_to_field_rm(fld, lambda default: True)
                for fld in dc_fields(tp)
            ),
            getter_kind=GetterKind.ATTR,
        )


class ClassInitFieldsProvider(TypeOnlyInputFFProvider):
    def _get_input_fields_figure(self, tp):
        if not isinstance(tp, type):
            raise CannotProvide

        try:
            return replace(
                get_func_iff(
                    tp.__init__, slice(1, None)
                ),
                constructor=tp,
            )
        except ValueError:
            raise CannotProvide