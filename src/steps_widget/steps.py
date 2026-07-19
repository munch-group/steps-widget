import dis
import types
import sys
import re
import inspect
import typing
import copy
import pprint
import os
import random
import time


# TODO: there should be no parentheses around single variables, function calls, method calls, literals

def _push(_stack, _expr, _evl):
    _gl = globals()
    _is_callable = isinstance(_expr, typing.Hashable) and _expr in _gl and callable(_gl[_expr])
    try:
        _is_builtin_fun = type(eval(_expr)) is types.BuiltinFunctionType
    except:
        _is_builtin_fun = False
    _is_builtit_class = _expr in ['int', 'float', 'str', 'list', 'dict', 'set', 'range', 'bool', 'map'] #eval(_expr).__class__.__module__ in ['__builtin__', 'builtins']
    _is_user_object = isinstance(_expr, typing.Hashable) and _expr in _gl and _gl[_expr].__class__.__module__ not in ['__builtin__', 'builtins']
    _get_attr_expr = re.match(r'^(\w+)\.(\w+)$', _expr)

    # print(_evl, _expr, _is_callable, _is_builtin_fun, _is_builtit_class, _is_user_object, _get_attr_expr)

    # fmt = f'{{:^{len(expr)}}}'
    _fmt = f'{{}}'
    if _evl and not _is_callable and not _is_builtin_fun and not _is_user_object and not _is_builtit_class:
        _stack.append(_fmt.format(repr(eval(_expr))))
    elif _evl and _get_attr_expr:
        # to handle that we cannot subsitute user def obj so that obj.attr needs to be handled as one substitution
        _obj, _attr = _get_attr_expr.groups()
        _stack.append(_fmt.format(repr(getattr(globals()[_obj], _attr))))
    else:
        _stack.append(_expr)

def _offset_to_index(_instructions, _target_offset):
    # jump-target opargs are byte offsets into the code object; instructions
    # are not fixed-width from 3.11+ (adaptive-interpreter CACHE entries make
    # the byte stride between instructions non-uniform), so jump targets must
    # be resolved to a list index by matching .offset rather than by dividing
    # the byte offset by an assumed instruction width.
    for _idx, _inst in enumerate(_instructions):
        if _inst.offset == _target_offset:
            return _idx
    raise ValueError(f"no instruction at offset {_target_offset}")

def _call_function(_stack, _instructions, _idx, _prefix, _evl):
    _args = [_stack.pop() for _ in range(_instructions[_idx].arg)][::-1]
    _fun = _stack.pop()
    _expr = f"{_fun}({', '.join(_args)})"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_add(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} + {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_substract(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} - {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_multiply(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} * {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_true_divide(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} / {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_floor_divide(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} // {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_modulo(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a} % {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_power(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    _expr = f'{_a}**{_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _is_op(_stack, _instructions, _idx, _prefix, _evl):
    _b = _stack.pop()
    _a = _stack.pop()
    if _instructions[_idx].argval == 1:
        _expr = f'{_a} is not {_b}'
    else:
        _expr = f'{_a} is {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _load_name(_stack, _instructions, _idx, _prefix, _evl):
    _expr = _instructions[_idx].argrepr
    # save the values of variables when they are first loaded
    # so they can be reset to their original value
    global _orig_values
    if _expr in globals():
        _val = globals()[_expr]
        if _expr not in _orig_values:
            _orig_values[_expr] = _val # save the orig val (could be important if it is a list or dict)
            globals()[_expr] = copy.deepcopy(_val) # make a dummy copy val
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _load_const(_stack, _instructions, _idx, _prefix, _evl):
    _const = _instructions[_idx].argval
    if isinstance(_const, types.CodeType):
        _stack.append(_const)
    else:
        _stack.append(repr(_const))
    return _idx+1, None

# def _make_function(_stack, _codeobj, _offset, _prefix, _evl):
#     _fun_name = _stack.pop()[2:-2]
#     _fun_codeobj = _stack.pop()

#     # print(_codeobj.co_varnames)
#     # pprint.pprint(list(dis.get_instructions(_codeobj)))

#     _fun_inst = list(dis.get_instructions(_fun_codeobj))
#     pprint.pprint(_fun_inst)

#     _fun_offset = 0
#     _fun_stack = []
#     while _fun_offset <= 2*(len(_fun_inst)-1):
#         print('local:', _fun_inst[_fun_offset//2].opname)
#         _fun_offset, _result = _inst_map[_fun_inst[_fun_offset//2].opname](_fun_stack, _fun_codeobj, _fun_offset, '', False)
#     _fun_expr = _result
#     print(_fun_expr)

#     exec(f'def {_fun_name}(arg):\\n    return {_fun_expr}\\n')
#     _fun = locals()[_fun_name]
#     _stack.append(_fun)
#     return _offset+2, None

# def _load_fast(_stack, _codeobj, _offset, _prefix, _evl):
#     _inst = list(dis.get_instructions(_codeobj))

#     _val = _stack.pop()
#     _var = _inst[_offset//2].argval
#     globals()[_var] = eval(_val)
#     _stack.append(_var)
#     return _offset+2, None

# def _for_iter(_stack, _codeobj, _offset, _prefix, _evl):
# #TOS is an iterator. Call its __next__() method. If this yields a new value,
# # push it on the stack (leaving the iterator below it). If the iterator indicates
# # it is exhausted, TOS is popped, and the byte code counter is incremented by delta.
#     _inst = list(dis.get_instructions(_codeobj))

#     _var = _stack.pop()
#     _stack.append(iter(globals()[_var]))
#     _iter = _stack[-1]
#     print(_iter)
#     try:
#         _val = next(_iter)
#         _stack.append(_val)
#         print(_stack)
#         return _offset+2, None
#     except StopIteration:
#         _stack.pop()
#         return _inst[_offset//2].argval, None

def _binary_subscr(_stack, _instructions, _idx, _prefix, _evl):
    _idx_val = _stack.pop()
    _var = _stack.pop()
    _expr = f"{_var}[{_idx_val}]"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _build_slice(_stack, _instructions, _idx, _prefix, _evl):
    _args = [_stack.pop() for _ in range(_instructions[_idx].arg)]
    _args = [x if x != 'None' else '' for x in _args[::-1]]
    _expr = ':'.join(_args)
    _stack.append(_expr)
    return _idx+1, None

def _load_method(_stack, _instructions, _idx, _prefix, _evl):
    _const = _instructions[_idx].argrepr
    _stack.append(_const)
    return _idx+1, None

def _load_attr(_stack, _instructions, _idx, _prefix, _evl):
    _attr = _instructions[_idx].argrepr
    _obj = _stack.pop()
    _expr = f'{_obj}.{_attr}'
    # save the values of variables when they are first loaded
    # so they can be reset to their original value
    global _orig_attr_values
    if _obj not in _orig_attr_values:
        _orig_attr_values[_obj] = {}
        if _attr not in _orig_attr_values[_obj]:
            _orig_attr_values[_obj][_attr] = getattr(globals()[_obj], _attr) # save the orig val (could be important if it is a list or dict)
            setattr(globals()[_obj], _attr, copy.deepcopy(getattr(globals()[_obj], _attr))) # make a dummy copy val
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _call_method(_stack, _instructions, _idx, _prefix, _evl):
    _args = [_stack.pop() for _ in range(_instructions[_idx].arg)]
    _method = _stack.pop()
    _var = _stack.pop()
    _expr = f"{_var}.{_method}({', '.join(_args)})"
    _push(_stack, _expr, _evl)
    return _idx+1, None

# not
def _unary_not(_stack, _instructions, _idx, _prefix, _evl):
    _var = _stack.pop()
    _expr = f"not {_var}"
    _push(_stack, _expr, _evl)
    return _idx+1, None

# and
def _jump_if_false_or_pop(_stack, _instructions, _idx, _prefix, _evl):
    _a = _stack.pop()
    # print(_evl, str(eval(_a)) == _a, _idx)
    if not eval(_a):
        # print(_a, 'is False. So moving to other side of "and"')
        _push(_stack, _a, _evl)
        if _evl:
            _result = f'... bool({_a}) is False, this terminates logic sequence with {_a} as result'
        else:
            _result = None
        return _offset_to_index(_instructions, _instructions[_idx].argval), _result
    if _evl and str(eval(_a)) == _a:
        _result = f'... bool({_a}) is True, evaluation moves to right side of closest "and"'
    else:
        _result = f'{_a}'
    return _idx+1, _result

# or
def _jump_if_true_or_pop(_stack, _instructions, _idx, _prefix, _evl):
    _a = _stack.pop()
    if eval(_a):
        _push(_stack, _a, _evl)
        if _evl:
            _result = f'... bool({_a}) is True, this terminates logic sequence with {_a} as result'
        else:
            _result = None
        return _offset_to_index(_instructions, _instructions[_idx].argval), _result
    if _evl and str(eval(_a)) == _a:
        _result = f'... bool({_a}) is False, evaluation moves to right side of closest "or"'
    else:
        _result = f'{_a}'
    return _idx+1, _result

# skip from right side of and to other side of or
def _pop_jump_if_false(_stack, _instructions, _idx, _prefix, _evl):
    _a = _stack.pop()
    if not eval(_a):
        # print('skipping', _a)
        if _evl:
            _result = f'... bool({_a}) is False, evaluation moves to right side of closest "or"'
            # _result = f'... bool({_a}) is False, this terminates logic sequence with {_a} as result'
        else:
            _result = f'{_a}'
        return _offset_to_index(_instructions, _instructions[_idx].argval), _result
    if _evl and str(eval(_a)) == _a:
        # _result = f'... bool({_a}) is True, evaluation moves to right side of "or")'
        # _result = f'... bool({_a}) is True, evaluation moves to right side of "and"'
        _result = f'... bool({_a}) is True, evaluation moves to right side of closest "and"'
    else:
        _result = f'{_a}'
    return _idx+1, _result


# # skip entire and
# def _pop_jump_if_false(_stack, _codeobj, _offset, _prefix, _evl):
#     _inst = list(dis.get_instructions(_codeobj))
#     _a = _stack.pop()
#     if not eval(_a):
#         return _inst[_offset//2].argval, None
#     return _offset+2, None



def _dup_top(_stack, _instructions, _idx, _prefix, _evl):
    _stack.append(_stack[-1])
    return _idx+1, None

def _compare_op(_stack, _instructions, _idx, _prefix, _evl):
    _op = _instructions[_idx].argrepr
    _b = _stack[-1]#.pop()
    _a = _stack[-2]#.pop()
    _expr = f'{_a} {_op} {_b}'
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _rot_two(_stack, _instructions, _idx, _prefix, _evl):
    _stack[-1], _stack[-2] = _stack[-2], _stack[-1]
    return _idx+1, None

def _rot_three(_stack, _instructions, _idx, _prefix, _evl):
    _stack[-1], _stack[-2], _stack[-3] = _stack[-2], _stack[-3],  _stack[-1]
    return _idx+1, None

def _pop_top(_stack, _instructions, _idx, _prefix, _evl):
    _stack.pop()
    return _idx+1, None

def _jump_forward(_stack, _instructions, _idx, _prefix, _evl):
    return _offset_to_index(_instructions, _instructions[_idx].argval), None

def _build_list(_stack, _instructions, _idx, _prefix, _evl):
    _args = [_stack.pop() for _ in range(_instructions[_idx].arg)][::-1]
    _stack.append(f'[{", ".join(_args)}]'), None
    return _idx+1, None

def _list_extend(_stack, _instructions, _idx, _prefix, _evl):
    _vals = _stack.pop()
    _lst = _stack.pop()
    if _instructions[_idx-1].opname == 'BUILD_LIST': # to get [1, 2, 3] _instead of [].extend((1, 2, 3))
        _expr = f"[{', '.join(map(str, eval(_vals)))}]"
    else:
        _expr = f"{_lst}.extend({_vals})"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _build_const_key_map(_stack, _instructions, _idx, _prefix, _evl):
    _keys = _stack.pop()
    _vals = [_stack.pop() for _ in range(_instructions[_idx].arg)][::-1]
    _keys = list(map(repr, eval(_keys)))
    _lst = []
    for _k, _v in zip(_keys, _vals):
        _lst.append(f"{_k}: {_v}")
    _expr = f"{{{', '.join(_lst)}}}"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_and(_stack, _instructions, _idx, _prefix, _evl):
    _a = _stack.pop()
    _b = _stack.pop()
    _expr = f"{_b} & {_a}"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_or(_stack, _instructions, _idx, _prefix, _evl):
    _a = _stack.pop()
    _b = _stack.pop()
    _expr = f"{_b} | {_a}"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _return_value(_stack, _instructions, _idx, _prefix, _evl):
    _result = _stack[-1]#.pop()
    # result = re.sub(r'(\s+)([.[{])', r'\2', result)
    # result = re.sub(r'(\S+[(])(\s+)', r'\1', result)
    # result = re.sub(r'(\s+)([)])', r'\2', result)
    return _idx+1, _prefix + _result

_inst_map = {
    'LOAD_CONST': _load_const,
    'LOAD_NAME': _load_name,
    'CALL_FUNCTION': _call_function,
    'IS_OP': _is_op,
    'BINARY_ADD': _binary_add,
    'BINARY_SUBTRACT': _binary_substract,
    'BINARY_MULTIPLY': _binary_multiply,
    'BINARY_POWER': _binary_power,
    'RETURN_VALUE': _return_value,
    'BINARY_SUBSCR': _binary_subscr,
    'BUILD_SLICE': _build_slice,
    'CALL_METHOD': _call_method,
    'LOAD_METHOD': _load_method,
    'LOAD_ATTR': _load_attr,
    'BINARY_TRUE_DIVIDE': _binary_true_divide,
    'BINARY_FLOOR_DIVIDE': _binary_floor_divide,
    'BINARY_MODULO': _binary_modulo,
    'UNARY_NOT': _unary_not,
    'BUILD_LIST': _build_list,
    'LIST_EXTEND': _list_extend,
    'BUILD_CONST_KEY_MAP': _build_const_key_map,
    'JUMP_IF_FALSE_OR_POP': _jump_if_false_or_pop,
    'JUMP_IF_TRUE_OR_POP': _jump_if_true_or_pop,
    'POP_JUMP_IF_FALSE': _pop_jump_if_false,
    'DUP_TOP': _dup_top,
    'ROT_THREE': _rot_three,
    'COMPARE_OP': _compare_op,
    'ROT_TWO': _rot_two,
    'POP_TOP': _pop_top,
    'JUMP_FORWARD': _jump_forward,
    'BINARY_OR': _binary_or,
    'BINARY_AND': _binary_and,
    # 'MAKE_FUNCTION': _make_function,
    # 'LOAD_FAST': _load_fast,
    # 'FOR_ITER': _for_iter,
}

_inst_type = {
    'LOAD_CONST': '',
    'LOAD_NAME': 'Substitution',
    'CALL_FUNCTION': 'Substitution',
    'IS_OP': 'Reduction',
    'BINARY_ADD': 'Reduction',
    'BINARY_SUBTRACT': 'Reduction',
    'BINARY_MULTIPLY': 'Reduction',
    'BINARY_POWER': 'Reduction',
    'RETURN_VALUE': 'Reduction',
    'BINARY_SUBSCR': 'Substitution',
    'BUILD_SLICE': 'Substitution',
    'CALL_METHOD': 'Substitution',
    'LOAD_METHOD': '',
    'LOAD_ATTR': 'Substitution',
    'BINARY_TRUE_DIVIDE': 'Reduction',
    'BINARY_FLOOR_DIVIDE': 'Reduction',
    'BINARY_MODULO': 'Reduction',
    'UNARY_NOT': 'Reduction',
    'BUILD_LIST': '',
    'LIST_EXTEND': '',
    'BUILD_CONST_KEY_MAP': '',
    'JUMP_IF_FALSE_OR_POP': 'Logic',
    'JUMP_IF_TRUE_OR_POP': 'Logic',
    'POP_JUMP_IF_FALSE': 'Logic',
    'DUP_TOP': '',
    'ROT_THREE': '',
    'COMPARE_OP': 'Reduction',
    'ROT_TWO': '',
    'POP_TOP': '',
    'JUMP_FORWARD': '',
    'BINARY_AND': 'Reduction',
    'BINARY_OR': 'Reduction',
    # 'MAKE_FUNCTION': _make_function,
    # 'LOAD_FAST': _load_fast,
    # 'FOR_ITER': _for_iter,
}

# --------------------------------------------------------------------------- #
# Python 3.11 dispatch table
#
# 3.11 renames/restructures a chunk of the opcodes above (documented per
# handler below) but keeps the rest byte-for-byte identical to 3.9/3.10 --
# confirmed empirically by disassembling this tool's supported expression
# grammar under a real 3.11 interpreter. Handlers are only written for what
# actually changed; everything else is inherited unchanged from
# _inst_map/_inst_type via the dict(...) copy below.
# --------------------------------------------------------------------------- #

# sentinel PUSH_NULL pushes onto the stack to mark "this call has no bound
# receiver" -- an object-identity check (never ==), so it can never collide
# with a legitimate stack value (always a string, or -- for LOAD_CONST of a
# nested code object -- a types.CodeType).
_NULL_SENTINEL = object()

def _resume(_stack, _instructions, _idx, _prefix, _evl):
    # RESUME opens every 3.11+ code object; pure interpreter bookkeeping, no
    # stack effect.
    return _idx+1, None

def _push_null(_stack, _instructions, _idx, _prefix, _evl):
    # Precedes a plain-callable call (`func(...)`) as opposed to a
    # `recv.method(...)` call compiled through LOAD_METHOD, so the later CALL
    # can tell the two shapes apart -- see _make_call.
    _stack.append(_NULL_SENTINEL)
    return _idx+1, None

def _precall(_stack, _instructions, _idx, _prefix, _evl):
    # Exists only for the adaptive interpreter's specialization machinery;
    # CPython's own docs describe it as a no-op. Removed again in 3.12.
    return _idx+1, None

_BINARY_OP_FORMATS = {
    '+': '{a} + {b}',
    '-': '{a} - {b}',
    '*': '{a} * {b}',
    '**': '{a}**{b}',
    '/': '{a} / {b}',
    '//': '{a} // {b}',
    '%': '{a} % {b}',
    '&': '{a} & {b}',
    '|': '{a} | {b}',
    '^': '{a} ^ {b}',
    '<<': '{a} << {b}',
    '>>': '{a} >> {b}',
}

def _binary_op(_stack, _instructions, _idx, _prefix, _evl):
    # 3.11 collapses BINARY_ADD/SUBTRACT/MULTIPLY/.../BINARY_AND/OR into one
    # BINARY_OP opcode; argrepr is already the clean operator symbol (e.g.
    # '+', '**', '&'), confirmed for every op this tool's grammar can produce.
    _op = _instructions[_idx].argrepr
    _b = _stack.pop()
    _a = _stack.pop()
    _fmt = _BINARY_OP_FORMATS.get(_op, '{a} ' + _op + ' {b}')
    _expr = _fmt.format(a=_a, b=_b)
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _call(_stack, _instructions, _idx, _prefix, _evl):
    # 3.11+ collapses CALL_FUNCTION/CALL_METHOD into one CALL opcode, with
    # two non-arg items sitting below the args. For a plain call
    # (func(...)), one of those two is the _NULL_SENTINEL PUSH_NULL pushed
    # -- *which* of the two pop positions it lands in flips between
    # 3.11/3.12 (pushed below the callable, so popped second) and 3.13
    # (pushed above it, so popped first) -- verified empirically. Rather
    # than track that flip with a per-era flag, both pops are checked for
    # sentinel identity directly, so this one function is correct for every
    # era without needing to know which. For a method call
    # (recv.method(...)), *neither* pop is ever the sentinel -- LOAD_METHOD
    # (3.11) and method-flagged LOAD_ATTR (3.12+) never emit PUSH_NULL --
    # and this module's own handlers for those opcodes always leave
    # [receiver, method_name] on the stack in that order regardless of era
    # (a convention this module chooses, not something read off real
    # CPython's stack layout), so there's no equivalent order-flip to
    # resolve for that branch.
    _args = [_stack.pop() for _ in range(_instructions[_idx].arg)][::-1]
    _first = _stack.pop()
    _second = _stack.pop()
    if _first is _NULL_SENTINEL or _second is _NULL_SENTINEL:
        _callee = _second if _first is _NULL_SENTINEL else _first
        _expr = f"{_callee}({', '.join(_args)})"
    else:
        _receiver, _callee = _second, _first
        _expr = f"{_receiver}.{_callee}({', '.join(_args)})"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _copy(_stack, _instructions, _idx, _prefix, _evl):
    # COPY(n): push a duplicate of the item n-deep. Replaces DUP_TOP (n=1)
    # and, combined with SWAP, the DUP_TOP+ROT_THREE pair the chained-
    # comparison idiom used pre-3.11 -- verified the SWAP(2)+COPY(2) sequence
    # produces the identical stack shape DUP_TOP+ROT_THREE did.
    _n = _instructions[_idx].arg
    _stack.append(_stack[-_n])
    return _idx+1, None

def _swap(_stack, _instructions, _idx, _prefix, _evl):
    # SWAP(n): swap TOS with the item n-deep. Replaces ROT_TWO (n=2) and,
    # combined with COPY, the DUP_TOP+ROT_THREE pair (see _copy).
    _n = _instructions[_idx].arg
    _stack[-1], _stack[-_n] = _stack[-_n], _stack[-1]
    return _idx+1, None

_inst_map_311 = dict(_inst_map)
_inst_map_311.update({
    'RESUME': _resume,
    'PUSH_NULL': _push_null,
    'PRECALL': _precall,
    'BINARY_OP': _binary_op,
    'CALL': _call,
    'COPY': _copy,
    'SWAP': _swap,
    # and/or short-circuiting for a *mixed* "a and b or c"-shaped expression
    # already lowers to POP_JUMP_IF_FALSE on 3.9/3.10 (registered above,
    # previously untested) -- 3.11 just renames it, since jumps became
    # direction-qualified. This grammar never produces backward jumps
    # (no loops), but registering the backward name too is free and
    # harmless, since the handler doesn't care about jump direction. There is
    # no POP_JUMP_..._IF_TRUE registration here: verified empirically that
    # 3.11 never emits it for and/or of this grammar (still uses
    # JUMP_IF_TRUE_OR_POP for that case) -- it only appears from 3.12 on,
    # where the whole and/or lowering is restructured.
    'POP_JUMP_FORWARD_IF_FALSE': _pop_jump_if_false,
    'POP_JUMP_BACKWARD_IF_FALSE': _pop_jump_if_false,
})
# opcodes 3.11 no longer produces for this tool's expression grammar --
# removed rather than left dangling, so the table only ever contains opcodes
# real 3.11 bytecode can actually emit.
for _opname in (
    'CALL_FUNCTION', 'CALL_METHOD', 'DUP_TOP', 'ROT_TWO', 'ROT_THREE',
    'BINARY_ADD', 'BINARY_SUBTRACT', 'BINARY_MULTIPLY', 'BINARY_POWER',
    'BINARY_TRUE_DIVIDE', 'BINARY_FLOOR_DIVIDE', 'BINARY_MODULO',
    'BINARY_AND', 'BINARY_OR', 'POP_JUMP_IF_FALSE',
):
    _inst_map_311.pop(_opname, None)

_inst_type_311 = dict(_inst_type)
_inst_type_311.update({
    'RESUME': '',
    'PUSH_NULL': '',
    'PRECALL': '',
    'BINARY_OP': 'Reduction',
    'CALL': 'Substitution',
    'COPY': '',
    'SWAP': '',
    'POP_JUMP_FORWARD_IF_FALSE': 'Logic',
    'POP_JUMP_BACKWARD_IF_FALSE': 'Logic',
})
for _opname in (
    'CALL_FUNCTION', 'CALL_METHOD', 'DUP_TOP', 'ROT_TWO', 'ROT_THREE',
    'BINARY_ADD', 'BINARY_SUBTRACT', 'BINARY_MULTIPLY', 'BINARY_POWER',
    'BINARY_TRUE_DIVIDE', 'BINARY_FLOOR_DIVIDE', 'BINARY_MODULO',
    'BINARY_AND', 'BINARY_OR', 'POP_JUMP_IF_FALSE',
):
    _inst_type_311.pop(_opname, None)

# --------------------------------------------------------------------------- #
# Python 3.12/3.13 dispatch table
#
# 3.12 restructures things 3.11 left alone: LOAD_METHOD is folded into
# LOAD_ATTR, PRECALL is dropped, 2-argument slicing gets its own opcode, and
# -- the biggest change -- JUMP_IF_FALSE_OR_POP/JUMP_IF_TRUE_OR_POP disappear
# entirely, replaced by a COPY+POP_JUMP_IF_FALSE/TRUE+POP_TOP idiom that now
# implements *every* and/or/chained-comparison short-circuit shape uniformly
# (previously split across several opcodes with role-specific narrative
# text -- see _pop_jump_if_false_312/_pop_jump_if_true_312 below for why
# that text has to become role-agnostic here). 3.13 adds one more opcode
# (TO_BOOL) into that same idiom but is otherwise identical to 3.12 for this
# tool's grammar, confirmed empirically -- so 3.13's table is built as a
# two-entry diff on top of 3.12's rather than a separate table.
# --------------------------------------------------------------------------- #

def _load_attr_312(_stack, _instructions, _idx, _prefix, _evl):
    # LOAD_METHOD is gone from 3.12 on; LOAD_ATTR itself now carries a
    # low-bit flag (surfaced only indirectly via dis -- argrepr gets a
    # "NULL|self"/"self|NULL" decoration when flagged, argval never does)
    # marking "this attribute access is a method-call site". argval is used
    # for the name in both branches -- never argrepr, whose decoration text
    # even changes word order between 3.12 and 3.13 (confirmed empirically)
    # -- and argrepr != argval is used purely as a presence check for the
    # flag, not parsed for content.
    _inst = _instructions[_idx]
    _attr = _inst.argval
    if _inst.argrepr != _attr:
        # method-call shape: leave the receiver on the stack and push just
        # the method name as an extra item, exactly like _load_method does
        # for 3.11's genuine LOAD_METHOD -- this is what lets _call's
        # method-call branch keep working unchanged.
        _stack.append(_attr)
        return _idx+1, None
    _obj = _stack.pop()
    _expr = f'{_obj}.{_attr}'
    global _orig_attr_values
    if _obj not in _orig_attr_values:
        _orig_attr_values[_obj] = {}
        if _attr not in _orig_attr_values[_obj]:
            _orig_attr_values[_obj][_attr] = getattr(globals()[_obj], _attr)
            setattr(globals()[_obj], _attr, copy.deepcopy(getattr(globals()[_obj], _attr)))
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _binary_slice(_stack, _instructions, _idx, _prefix, _evl):
    # Replaces BUILD_SLICE+BINARY_SUBSCR, but only for 2-argument slicing --
    # x[1:2:3] still routes through BUILD_SLICE+BINARY_SUBSCR unchanged on
    # every version (confirmed empirically), so those two handlers are
    # reused as-is for the 3-argument case.
    _stop = _stack.pop()
    _start = _stack.pop()
    _var = _stack.pop()
    _expr = f"{_var}[{_start}:{_stop}]"
    _push(_stack, _expr, _evl)
    return _idx+1, None

def _pop_jump_if_false_312(_stack, _instructions, _idx, _prefix, _evl):
    # 3.12 retires JUMP_IF_FALSE_OR_POP/JUMP_IF_TRUE_OR_POP entirely --
    # COPY(1) [+ TO_BOOL on 3.13] + POP_JUMP_IF_FALSE/TRUE + POP_TOP now
    # implements *every* and/or/chained-comparison short-circuit shape this
    # tool's grammar produces, not just the "mixed and-then-or" case
    # POP_JUMP_IF_FALSE alone used to cover pre-3.12 (see
    # _pop_jump_if_false above, unchanged and still used for that one role
    # on 3.9/3.10/3.11). Narrative text below is deliberately role-agnostic
    # (doesn't claim "moves to right side of and/or") because the *same*
    # opcode now plays the isolated-and, mixed-and-then-or, *and*
    # chained-comparison role depending on context, verified empirically by
    # disassembling all three shapes. POP_JUMP_IF_FALSE always pops
    # unconditionally and never re-pushes in either branch -- the value
    # COPY duplicated stays underneath for whichever of POP_TOP
    # (fallthrough) or the jump target (short-circuit) consumes it next, so
    # nothing needs pushing back here either.
    #
    # The short-circuit branch's result is None (not the bare value) at low
    # _evl, mirroring _jump_if_false_or_pop rather than _pop_jump_if_false:
    # unlike the legacy mixed-and/or case, this opcode's jump target can now
    # land *directly* on RETURN_VALUE (isolated "and"/"or"), and returning a
    # non-None result here would break the walk right at this instruction,
    # before RETURN_VALUE is ever reached to register its own dedup key --
    # producing a spurious extra step once a later outer iteration's walk
    # finally continues past this (already-deduped) jump down to
    # RETURN_VALUE. Deferring to None here lets the walk fall through to
    # RETURN_VALUE at low reveal too, exactly like the legacy isolated-and
    # case already does.
    _a = _stack.pop()
    _target_idx = _offset_to_index(_instructions, _instructions[_idx].argval)
    if not eval(_a):
        if _evl:
            if _instructions[_target_idx].opname == 'RETURN_VALUE':
                # jump target is the expression's own return -- this really
                # is the terminal case (isolated "and"/"or"), so it gets the
                # same wording _jump_if_false_or_pop uses pre-3.12 for the
                # identical role.
                _result = f'... bool({_a}) is False, this terminates logic sequence with {_a} as result'
            else:
                # jump target is more logic-checking code (mixed
                # and-then-or, or a chained comparison's next hop) -- not
                # actually terminal, so the wording doesn't claim it is.
                _result = f'... bool({_a}) is False, short-circuits here with {_a}'
        else:
            _result = None
        return _target_idx, _result
    if _evl and str(eval(_a)) == _a:
        _result = f'... bool({_a}) is True, evaluation continues with the rest of the expression'
    else:
        _result = f'{_a}'
    return _idx+1, _result

def _pop_jump_if_true_312(_stack, _instructions, _idx, _prefix, _evl):
    # Symmetric to _pop_jump_if_false_312, for "or"'s truthy short-circuit --
    # genuinely new opcode role from 3.12 on, no 3.9/3.10/3.11 analog (those
    # eras use JUMP_IF_TRUE_OR_POP for this, which conditionally pops
    # instead of always popping).
    # See _pop_jump_if_false_312 for why the short-circuit branch defers to
    # None at low _evl, and for the target-opname check driving which
    # wording is used.
    _a = _stack.pop()
    _target_idx = _offset_to_index(_instructions, _instructions[_idx].argval)
    if eval(_a):
        if _evl:
            if _instructions[_target_idx].opname == 'RETURN_VALUE':
                _result = f'... bool({_a}) is True, this terminates logic sequence with {_a} as result'
            else:
                _result = f'... bool({_a}) is True, short-circuits here with {_a}'
        else:
            _result = None
        return _target_idx, _result
    if _evl and str(eval(_a)) == _a:
        _result = f'... bool({_a}) is False, evaluation continues with the rest of the expression'
    else:
        _result = f'{_a}'
    return _idx+1, _result

def _to_bool(_stack, _instructions, _idx, _prefix, _evl):
    # True no-op for this symbolic engine: real TO_BOOL replaces TOS with
    # bool(TOS), but eval()-ing the *original* text already produces the
    # same truthiness the narrative handlers above need, and keeping the
    # original text (e.g. "0") rather than substituting "False" reads
    # better, not less correctly.
    return _idx+1, None

_inst_map_312 = dict(_inst_map_311)
_inst_map_312.update({
    'LOAD_ATTR': _load_attr_312,
    'BINARY_SLICE': _binary_slice,
    'POP_JUMP_IF_FALSE': _pop_jump_if_false_312,
    'POP_JUMP_IF_TRUE': _pop_jump_if_true_312,
})
# opcodes that existed on 3.11 but are gone by 3.12: LOAD_METHOD (folded
# into LOAD_ATTR), PRECALL (dropped), the FORWARD/BACKWARD-qualified
# POP_JUMP names (unified back into plain POP_JUMP_IF_FALSE, now registered
# above), and JUMP_IF_FALSE_OR_POP/JUMP_IF_TRUE_OR_POP (fully retired --
# every and/or/chained-comparison shape goes through POP_JUMP_IF_FALSE/TRUE
# now, confirmed empirically for every shape this grammar produces).
for _opname in (
    'LOAD_METHOD', 'PRECALL', 'POP_JUMP_FORWARD_IF_FALSE',
    'POP_JUMP_BACKWARD_IF_FALSE', 'JUMP_IF_FALSE_OR_POP',
    'JUMP_IF_TRUE_OR_POP',
):
    _inst_map_312.pop(_opname, None)

_inst_type_312 = dict(_inst_type_311)
_inst_type_312.update({
    'LOAD_ATTR': 'Substitution',
    'BINARY_SLICE': 'Substitution',
    'POP_JUMP_IF_FALSE': 'Logic',
    'POP_JUMP_IF_TRUE': 'Logic',
})
for _opname in (
    'LOAD_METHOD', 'PRECALL', 'POP_JUMP_FORWARD_IF_FALSE',
    'POP_JUMP_BACKWARD_IF_FALSE', 'JUMP_IF_FALSE_OR_POP',
    'JUMP_IF_TRUE_OR_POP',
):
    _inst_type_312.pop(_opname, None)

# 3.13 is a two-entry diff on top of 3.12: TO_BOOL is inserted into the
# and/or/chained-comparison idiom (harmless to register even though nothing
# else changes -- see _to_bool above).
_inst_map_313 = dict(_inst_map_312)
_inst_map_313['TO_BOOL'] = _to_bool

_inst_type_313 = dict(_inst_type_312)
_inst_type_313['TO_BOOL'] = ''

# def find_parens(s):
#     toret = {}
#     pstack = []

#     for i, c in enumerate(s):
#         if c == '(':
#             pstack.append(i)
#         elif c == ')':
#             if len(pstack) == 0:
#                 raise IndexError("No matching closing parens at: " + str(i))
#             toret[pstack.pop()] = i

#     if len(pstack) > 0:
#         raise IndexError("No matching opening parens at: " + str(pstack.pop()))

#     return toret

def __paren(_expr):
    return _expr

_orig_values = {}
_orig_attr_values = {}

def _steps(_expr, _print_steps=False, _with_labels=False):

    # dispatch tables vary by CPython bytecode era -- pick the one that
    # matches the running interpreter once, up front.
    if (3, 9) <= sys.version_info < (3, 11):
        _era_inst_map = _inst_map
        _era_inst_type = _inst_type
        # DUP_TOP/ROT_TWO/ROT_THREE/POP_TOP/JUMP_FORWARD are pure internal
        # plumbing (comparison-chaining and jump bookkeeping) with no
        # standalone meaning of their own -- they belong here for the same
        # reason LOAD_CONST/LOAD_METHOD/etc. do. Without this,
        # _inst_type[...]='' alone does *not* suppress their label (see
        # _op_performed below: it only replaces a truthy mapped value, and
        # '' is falsy) -- their raw opcode names leak into the trace
        # instead, confirmed live for a chained comparison
        # (e.g. "[DUP_TOP] 2 < c" instead of a blank label).
        _era_non_oprations = [
            'LOAD_CONST', 'BUILD_SLICE', 'LOAD_METHOD', 'LOAD_ATTR',
            'DUP_TOP', 'ROT_TWO', 'ROT_THREE', 'POP_TOP', 'JUMP_FORWARD',
        ]
        _era_call_opname = 'CALL_FUNCTION'
        _era_logic_opnames = [
            'JUMP_IF_TRUE_OR_POP', 'JUMP_IF_FALSE_OR_POP', 'POP_JUMP_IF_FALSE',
        ]
    elif (3, 11) <= sys.version_info < (3, 12):
        _era_inst_map = _inst_map_311
        _era_inst_type = _inst_type_311
        # POP_TOP is included here (unlike in the legacy 3.9/3.10 list
        # above, until just now) because it now shows up in this era's
        # chained-comparison cleanup and would otherwise leak its raw
        # opcode name as a label the same way DUP_TOP/ROT_THREE do on
        # legacy -- _inst_type[...]='' alone doesn't suppress it, only
        # _non_oprations membership does (see _op_performed below).
        _era_non_oprations = [
            'LOAD_CONST', 'BUILD_SLICE', 'LOAD_METHOD', 'LOAD_ATTR',
            'RESUME', 'PUSH_NULL', 'PRECALL', 'COPY', 'SWAP', 'POP_TOP',
        ]
        _era_call_opname = 'CALL'
        # 3.11 keeps JUMP_IF_TRUE_OR_POP/JUMP_IF_FALSE_OR_POP unchanged and
        # renames POP_JUMP_IF_FALSE to POP_JUMP_FORWARD_IF_FALSE (jumps
        # became direction-qualified) -- verified empirically that this
        # grammar never produces a POP_JUMP_..._IF_TRUE variant on 3.11
        # (that only starts on 3.12, see the elif below), and never a
        # backward jump (no loops in this grammar), but the backward name
        # is included anyway since checking for it is free.
        _era_logic_opnames = [
            'JUMP_IF_TRUE_OR_POP', 'JUMP_IF_FALSE_OR_POP',
            'POP_JUMP_FORWARD_IF_FALSE', 'POP_JUMP_BACKWARD_IF_FALSE',
        ]
    elif (3, 12) <= sys.version_info < (3, 14):
        _era_inst_map = _inst_map_312 if sys.version_info < (3, 13) else _inst_map_313
        _era_inst_type = _inst_type_312 if sys.version_info < (3, 13) else _inst_type_313
        # POP_TOP is part of the and/or/chained-comparison idiom itself from
        # 3.12 on (see _pop_jump_if_false_312), not just chained-comparison
        # cleanup -- same reasoning as the 3.11 branch above, just a bigger
        # share of traces would otherwise be affected.
        _era_non_oprations = [
            'LOAD_CONST', 'BUILD_SLICE', 'LOAD_ATTR',
            'RESUME', 'PUSH_NULL', 'COPY', 'SWAP', 'POP_TOP',
        ]
        if sys.version_info >= (3, 13):
            _era_non_oprations.append('TO_BOOL')
        _era_call_opname = 'CALL'
        # JUMP_IF_TRUE_OR_POP/JUMP_IF_FALSE_OR_POP are fully retired from
        # 3.12 on -- every and/or/chained-comparison shape goes through
        # POP_JUMP_IF_FALSE/TRUE now (see _pop_jump_if_false_312).
        _era_logic_opnames = ['POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE']
    else:
        raise RuntimeError(
            "steps_widget's stepper dispatches on version-specific CPython "
            "bytecode opcode names. It currently has dispatch tables for "
            "Python 3.9 through 3.13 only -- this interpreter reports "
            f"{sys.version_info[0]}.{sys.version_info[1]}."
        )

    _step_list = []
    _label_list = []

    # _dictionaries holding the original values of variables and attributes
    global _orig_values
    global _orig_attr_values

    # subst white space for single space to produce correspondence between _expr and _result
    # _expr = re.sub(r'([+]+)', r' \g<1> ', _expr)
    _expr = re.sub(r'\s+(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)', r' ', _expr)
    # _expr = re.sub(r'\s+(?=([^"]*"[^"]*")*[^"]', r' ', _expr)

    # print the expression
    if _print_steps:
        print(f"{'As written:'.ljust(15)}  {_expr}", file=sys.stderr)
    _step_list.append(_expr)
    _label_list.append('As written')

    # if it is an assignment statement, cut off the assignment part as a prefix
    _match = re.match(r'\s*\S+\s*[*/+-]?=\s*', _expr)
    if _match:
        _prefix = _match.group(0)
    else:
        _prefix = ''
    _expr = _expr[len(_prefix):]

    # disassembly
    _codeobj = dis.Bytecode(_expr).codeobj
    _instructions = list(dis.get_instructions(_codeobj))

    # last valid instruction index
    _max_idx = len(_instructions) - 1

    # nr of operations that should produce seperate steps
    _nr_operations = sum(inst.opname not in _era_non_oprations for inst in _instructions)

    # replace paretheses with __paren function calls
    # compares line produced from disassembly to expression
    # only parentheses that differ between the two are user parentheses
    _stack = []
    _idx = 0
    while _idx <= _max_idx:
        _idx, _result = _era_inst_map[_instructions[_idx].opname](_stack, _instructions, _idx, _prefix, False)
    _result = _result[len(_prefix):]
    _j = 0
    _paren_idx = []
    for _i in range(len(_expr)):
        if _expr[_i] == _result[_j] or (_expr[_i] in ['"', "'"] and _result[_j] in ['"', "'"]):
            _j += 1
        elif _expr[_i] == '(':
            _paren_idx.append(_i)
        if _j == len(_result):
            break
    for _i in reversed(_paren_idx):
        _expr = _expr[:_i] + '__paren' + _expr[_i:]
        break

    # pprint.pprint(_instructions)

    # redo disassembly on modified expression
    _codeobj = dis.Bytecode(_expr).codeobj
    _instructions = list(dis.get_instructions(_codeobj))
    _max_idx = len(_instructions) - 1
    _nr_operations = sum(inst.opname not in _era_non_oprations for inst in _instructions)

    # _prev_result = None
    _op_performed = 'Sub-expression'

    # set of (idx, result) tuples printed so far
    _prev_prints = set()

    # 0 if expression contains logic, 1 othewise -- opname list is
    # era-specific (_era_logic_opnames, set above) since which opcodes
    # actually implement and/or/chained-comparison short-circuiting varies
    # by CPython bytecode era. This previously hardcoded a single
    # 3.9/3.10-only list with a missing comma between the last two entries
    # ('JUMP_IF_FALSE_OR_POP' 'POP_JUMP_IF_FALSE', silently concatenated by
    # adjacent-string-literal syntax into one bogus never-matching name), so
    # POP_JUMP_IF_FALSE was never actually detected even on 3.9/3.10.
    _is_not_logic_expr = not any(inst.opname in _era_logic_opnames for inst in _instructions)

    for i in range(_nr_operations):
        _stack = []
        _nr_op = 0
        _idx = 0
        while _idx <= _max_idx:
            # __paren is always called with exactly one argument (see its
            # definition above), so its callable name sits at _stack[-2] in
            # every era except 3.13, where the identity/callee push order
            # flips (see _call) and it lands one slot deeper instead --
            # checking both positions keeps this correct across all of
            # 3.9/3.10 (no identity slot at all), 3.11/3.12 (identity
            # deeper), and 3.13 (identity shallower) without needing to
            # special-case any of them individually.
            _param_fun_call = _instructions[_idx].opname == _era_call_opname and len(_stack) >= 2 and (
                _stack[-2] == '__paren' or (len(_stack) >= 3 and _stack[-3] == '__paren')
            )
            if _instructions[_idx].opname not in _era_non_oprations and not _param_fun_call:
                _nr_op += 1
                if _nr_op == i:
                    _op_performed = _instructions[_idx].opname
            _idx, _result = _era_inst_map[_instructions[_idx].opname](_stack, _instructions, _idx, _prefix, _nr_op <= i)
            # print(_idx, _stack, _result)

            # print(i, _is_not_logic_expr)
            if _result is not None and (_idx, _result) not in _prev_prints:# and not (i == 0 and _is_not_logic_expr):

            # if _result is not None and _result != _prev_result:
                if _op_performed in _era_inst_type and _era_inst_type[_op_performed]:
                    _op_performed = _era_inst_type[_op_performed]

                _to_print = _result.replace('__paren', '')
                if not (_is_not_logic_expr and _op_performed == 'Sub-expression'):
                    _step_list.append(_to_print)
                    _label_list.append(_op_performed)
                    if _print_steps:
                        print(f"{(_op_performed+':').ljust(15)}  {_to_print}", file=sys.stderr)
                        # print(_to_print)

                # print(_result.replace('__paren', ''))
                # _prev_result = _result
                _prev_prints.add((_idx, _result))
                break

        globals().update(_orig_values)
        _orig_values = {}

        for obj in _orig_attr_values:
            for attr in _orig_attr_values[obj]:
                setattr(globals()[obj], attr, _orig_attr_values[obj][attr])
        _orig_attr_values = {}
    if _print_steps:
        print(file=sys.stderr)

    if _with_labels:
        return list(zip(_label_list, _step_list))
    return _step_list
