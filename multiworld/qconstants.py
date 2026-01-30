float_dir = [
    '__abs__', '__add__', '__bool__', '__ceil__', '__class__', '__delattr__', '__dir__', '__divmod__', '__doc__',
    '__eq__', '__float__', '__floor__', '__floordiv__', '__format__', '__ge__', '__getattribute__', '__getformat__',
    '__getnewargs__', '__getstate__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__int__', '__le__',
    '__lt__', '__mod__', '__mul__', '__ne__', '__neg__', '__new__', '__pos__', '__pow__', '__radd__', '__rdivmod__',
    '__reduce__', '__reduce_ex__', '__repr__', '__rfloordiv__', '__rmod__', '__rmul__', '__round__', '__rpow__',
    '__rsub__', '__rtruediv__', '__setattr__', '__sizeof__', '__str__', '__sub__', '__subclasshook__', '__truediv__',
    '__trunc__', 'as_integer_ratio', 'conjugate', 'fromhex', 'hex', 'imag', 'is_integer', 'real']

recip = {
    '__add__': '__radd__', '__divmod__': '__rdivmod__', '__floordiv__': '__rfloordiv__', '__mod__': '__rmod__',
    '__mul__': '__rmul__', '__pow__': '__rpow__', '__sub__': '__rsub__', '__truediv__': '__rtruediv__'}
rrecip = {v: k for k, v in recip.items()}
recip.update(rrecip)

float_methods = [
    '__abs__', '__add__', '__bool__', '__ceil__', '__divmod__', '__floor__',
    '__floordiv__', '__format__', '__int__', '__mod__', '__mul__', '__neg__', '__pos__', '__pow__',
    '__radd__', '__rdivmod__', '__reduce__', '__reduce_ex__', '__rfloordiv__', '__rmod__', '__rmul__', '__round__',
    '__rpow__', '__rsub__', '__rtruediv__', '__sub__', '__truediv__', '__trunc__', 'as_integer_ratio', 'conjugate',
    'fromhex', 'hex', 'is_integer', '__eq__', '__ne__', '__ge__', '__gt__', '__le__', '__lt__']

float_special = ['imag', 'real']

float_excluded = ['__complex__', '__float__']

complex_dir = [
    '__abs__', '__add__', '__bool__', '__class__', '__complex__', '__delattr__', '__dir__', '__doc__', '__eq__',
    '__format__', '__ge__', '__getattribute__', '__getnewargs__', '__getstate__', '__gt__', '__hash__', '__init__',
    '__init_subclass__', '__le__', '__lt__', '__mul__', '__ne__', '__neg__', '__new__', '__pos__', '__pow__',
    '__radd__', '__reduce__', '__reduce_ex__', '__repr__', '__rmul__', '__rpow__', '__rsub__', '__rtruediv__',
    '__setattr__', '__sizeof__', '__str__', '__sub__', '__subclasshook__', '__truediv__', 'conjugate', 'imag', 'real']

complex_methods = [
    '__abs__', '__add__', '__format__',
    '__mul__', '__neg__', '__pos__', '__pow__',
    '__radd__', '__reduce__', '__reduce_ex__', '__repr__', '__rmul__', '__rpow__', '__rsub__', '__rtruediv__',
    '__sub__', '__truediv__', 'conjugate', 'imag', 'real', '__eq__', '__ge__', '__gt__', '__le__', '__lt__', '__ne__'
]

complex_excluded = [
    '__class__', '__complex__', '__delattr__', '__dir__', '__doc__', '__getattribute__',
    '__getnewargs__', '__getstate__', '__hash__', '__init__', '__init_subclass__', '__new__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__'
]

sympy_dir = ['_Frel', '__abs__', '__add__', '__bool__', '__ceil__', '__divmod__', '__eq__', '__floor__', '__floordiv__', '__format__', '__ge__', '__gt__', '__int__', '__le__', '__lt__', '__mod__', '__mul__', '__ne__', '__neg__', '__pos__', '__pow__', '__radd__', '__rdivmod__', '__rfloordiv__', '__rmod__', '__rmul__', '__round__', '__rpow__', '__rsub__', '__rtruediv__', '__sub__', '__truediv__', '__trunc__', '_as_mpf_op', '_as_mpf_val', '_diff_wrt', '_do_eq_sympify', '_eval_adjoint', '_eval_as_leading_term', '_eval_conjugate', '_eval_derivative', '_eval_derivative_matrix_lines', '_eval_derivative_n_times', '_eval_evalf', '_eval_expand_complex', '_eval_interval', '_eval_is_algebraic_expr', '_eval_is_comparable', '_eval_is_extended_negative', '_eval_is_extended_positive', '_eval_is_extended_positive_negative', '_eval_is_finite', '_eval_is_infinite', '_eval_is_integer', '_eval_is_meromorphic', '_eval_is_negative', '_eval_is_polynomial', '_eval_is_positive', '_eval_is_rational_function', '_eval_is_zero', '_eval_lseries', '_eval_nseries', '_eval_order', '_eval_power', '_eval_rewrite', '_eval_simplify', '_eval_subs', '_eval_transpose', '_evalf', '_from_mpmath', '_mpf_', '_mul_handler', '_parse_order', '_pow', '_prec', '_random', '_remove_non_digits', '_rewrite', '_sage_', '_sorted_args', '_subs', '_to_mpmath', '_xreplace', 'adjoint', 'apart', 'args', 'args_cnc', 'as_base_exp', 'as_coeff_Add', 'as_coeff_Mul', 'as_coeff_add', 'as_coeff_exponent', 'as_coeff_mul', 'as_coefficient', 'as_coefficients_dict', 'as_content_primitive', 'as_dummy', 'as_expr', 'as_independent', 'as_leading_term', 'as_numer_denom', 'as_ordered_factors', 'as_ordered_terms', 'as_poly', 'as_powers_dict', 'as_real_imag', 'as_terms', 'aseries', 'assumptions0', 'atoms', 'canonical_variables', 'ceiling', 'class_key', 'coeff', 'cofactors', 'collect', 'combsimp', 'compare', 'conjugate', 'copy', 'could_extract_minus_sign', 'count', 'count_ops', 'default_assumptions', 'diff', 'dir', 'doit', 'dummy_eq', 'epsilon_eq', 'equals', 'evalf', 'expand', 'expr_free_symbols', 'extract_additively', 'extract_branch_factor', 'extract_multiplicatively', 'factor', 'find', 'floor', 'fourier_series', 'fps', 'free_symbols', 'fromiter', 'func', 'gammasimp', 'gcd', 'getO', 'getn', 'has', 'has_free', 'has_xfree', 'integrate', 'invert', 'is_Add', 'is_AlgebraicNumber', 'is_Atom', 'is_Boolean', 'is_Derivative', 'is_Dummy', 'is_Equality', 'is_Float', 'is_Function', 'is_Indexed', 'is_Integer', 'is_MatAdd', 'is_MatMul', 'is_Matrix', 'is_Mul', 'is_Not', 'is_Number', 'is_NumberSymbol', 'is_Order', 'is_Piecewise', 'is_Point', 'is_Poly', 'is_Pow', 'is_Rational', 'is_Relational', 'is_Symbol', 'is_Vector', 'is_Wild', 'is_algebraic', 'is_algebraic_expr', 'is_antihermitian', 'is_commutative', 'is_comparable', 'is_complex', 'is_composite', 'is_constant', 'is_even', 'is_extended_negative', 'is_extended_nonnegative', 'is_extended_nonpositive', 'is_extended_nonzero', 'is_extended_positive', 'is_extended_real', 'is_finite', 'is_hermitian', 'is_hypergeometric', 'is_imaginary', 'is_infinite', 'is_integer', 'is_irrational', 'is_meromorphic', 'is_negative', 'is_noninteger', 'is_nonnegative', 'is_nonpositive', 'is_nonzero', 'is_number', 'is_odd', 'is_polar', 'is_polynomial', 'is_positive', 'is_prime', 'is_rational', 'is_rational_function', 'is_real', 'is_same', 'is_scalar', 'is_symbol', 'is_transcendental', 'is_zero', 'kind', 'lcm', 'leadterm', 'limit', 'lseries', 'match', 'matches', 'n', 'normal', 'nseries', 'nsimplify', 'num', 'powsimp', 'primitive', 'radsimp', 'ratsimp', 'rcall', 'refine', 'removeO', 'replace', 'rewrite', 'round', 'separate', 'series', 'simplify', 'sort_key', 'subs', 'taylor_term', 'together', 'transpose', 'trigsimp', 'xreplace']

sympy_excluded = [
    '__annotations__', '__class__', '__complex__', '__delattr__', '__dir__', '__doc__', '__firstlineno__', '__float__', '__getattribute__', '__getnewargs__', '__getnewargs_ex__', '__getstate__', '__hash__', '__init__', '__init_subclass__', '__module__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__setstate__', '__sizeof__', '__slots__', '__static_attributes__', '__str__', '__subclasshook__', '__sympy__', '_add_handler', '_args', '_assumptions', '_constructor_postprocessor_mapping', '_exec_constructor_postprocessors', '_expand_hint', '_explicit_class_assumptions', '_has', '_hashable_content', '_mhash', '_new', '_op_priority', '_prop_handler', '_repr_disabled', '_repr_latex_', '_repr_png_', '_repr_svg_', 'cancel'
]

complex_arith = [
    '__abs__', '__add__', '__bool__', '__mul__', '__neg__',
    '__pos__', '__pow__', '__radd__', '__reduce__', '__reduce_ex__', '__rmul__', '__rpow__', '__rsub__', '__rtruediv__',
    '__sub__', '__truediv__', 'conjugate', 'imag', 'real']

complex_bool = ['__eq__', '__ge__', '__gt__', '__le__', '__lt__', '__ne__']

complex_other = [
    '__class__', '__complex__', '__delattr__', '__dir__', '__doc__', '__format__', '__getattribute__',
    '__getnewargs__', '__getstate__', '__hash__', '__init__', '__init_subclass__', '__new__', '__repr__',
    '__setattr__', '__sizeof__', '__str__', '__subclasshook__'
]

excluded_methods = {'__class__', '__eq__', '__getattribute__', '__init__', '__setattr__', '__subclasshook__', '__new__', '__dict__', '__module__', '__dir__', '__init_subclass__', '__delattr__', '__sizeof__', '__repr__', '__getstate__', 'real', 'imag', '__float__', '__complex__', '__ge__', '__le__'}

