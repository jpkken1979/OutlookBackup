#!/usr/bin/env python3
"""
Test Generator - Genera tests automáticamente basados en código fuente.

Uso:
    python test_generator.py --file src/module.py --output tests/test_module.py
    python test_generator.py --dir src/ --output-dir tests/
    python test_generator.py --file src/api.py --framework pytest --style aaa

Características:
    - Genera tests unitarios con estructura AAA (Arrange-Act-Assert)
    - Soporta pytest, unittest, jest
    - Detecta funciones y métodos automáticamente
    - Genera fixtures y mocks básicos
"""

import argparse
import ast
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Información de una función extraída del AST."""

    name: str
    args: list[str]
    returns: str | None = None
    docstring: str | None = None
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None
    decorators: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    """Representa un caso de test generado."""

    name: str
    function_name: str
    description: str
    arrange: str
    act: str
    assertions: list[str]


class CodeAnalyzer:
    """Analiza código Python para extraer funciones y métodos."""

    def __init__(self, source_code: str):
        self.source = source_code
        self.tree = ast.parse(source_code)
        self.functions: list[FunctionInfo] = []
        self._analyze()

    def _analyze(self) -> None:
        """Analiza el AST del código."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                self._extract_function(node)
            elif isinstance(node, ast.AsyncFunctionDef):
                self._extract_function(node, is_async=True)
            elif isinstance(node, ast.ClassDef):
                self._extract_class_methods(node)

    def _extract_function(
        self, node: ast.FunctionDef, is_async: bool = False, class_name: str | None = None
    ) -> None:
        """Extrae información de una función."""
        # Ignorar funciones privadas internas
        if node.name.startswith("__") and node.name.endswith("__"):
            if node.name not in ("__init__", "__call__"):
                return

        args = []
        for arg in node.args.args:
            if arg.arg != "self":
                args.append(arg.arg)

        # Obtener tipo de retorno si existe
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        # Obtener docstring
        docstring = ast.get_docstring(node)

        # Obtener decoradores
        decorators = [ast.unparse(d) for d in node.decorator_list]

        func_info = FunctionInfo(
            name=node.name,
            args=args,
            returns=returns,
            docstring=docstring,
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
            decorators=decorators,
        )
        self.functions.append(func_info)

    def _extract_class_methods(self, node: ast.ClassDef) -> None:
        """Extrae métodos de una clase."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._extract_function(item, class_name=node.name)
            elif isinstance(item, ast.AsyncFunctionDef):
                self._extract_function(item, is_async=True, class_name=node.name)


class TestGenerator:
    """Genera tests basados en el análisis de código."""

    PYTEST_TEMPLATE = '''#!/usr/bin/env python3
"""
Tests para {module_name}.

Generado automáticamente el {date}.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
{imports}


class Test{class_name}:
    """Tests para {class_name}."""

    @pytest.fixture
    def instance(self):
        """Crea instancia para tests."""
        return {class_name}()

{test_methods}
'''

    PYTEST_FUNCTION_TEMPLATE = '''
def test_{func_name}_basic():
    """Test basico para {func_name}."""
    # Arrange
    {arrange}

    # Act
    {act}

    # Assert
    {assertions}


def test_{func_name}_edge_cases():
    """Test de casos limite para {func_name}."""
    # Caso: argumentos None
    try:
        {func_name}(None)
    except (TypeError, ValueError):
        pass  # Excepcion esperada con None
'''

    PYTEST_METHOD_TEMPLATE = '''
    def test_{func_name}_success(self, instance):
        """Test exitoso de {func_name}."""
        # Arrange
        {arrange}

        # Act
        {act}

        # Assert
        {assertions}

    def test_{func_name}_failure(self, instance):
        """Test de fallo de {func_name}."""
        # Verificar manejo de argumentos invalidos
        with pytest.raises((TypeError, ValueError, AttributeError)):
            instance.{func_name}(None)
'''

    def __init__(self, framework: str = "pytest", style: str = "aaa"):
        self.framework = framework
        self.style = style

    def generate_tests(self, functions: list[FunctionInfo], module_name: str) -> str:
        """Genera código de tests para las funciones."""
        logger.info(f"Generando tests para {len(functions)} funciones")

        # Agrupar por clase
        class_functions: dict[str | None, list[FunctionInfo]] = {}
        for func in functions:
            key = func.class_name
            if key not in class_functions:
                class_functions[key] = []
            class_functions[key].append(func)

        output_parts = []

        # Header
        output_parts.append(self._generate_header(module_name))

        # Tests para funciones standalone
        if None in class_functions:
            for func in class_functions[None]:
                output_parts.append(self._generate_function_test(func))

        # Tests para clases
        for class_name, methods in class_functions.items():
            if class_name is None:
                continue
            output_parts.append(self._generate_class_tests(class_name, methods))

        return "\n".join(output_parts)

    def _generate_header(self, module_name: str) -> str:
        """Genera el header del archivo de tests."""
        return f'''#!/usr/bin/env python3
"""
Tests para {module_name}.

Generado automáticamente el {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.
Usa el patrón AAA (Arrange-Act-Assert).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from {module_name} import *

'''

    def _generate_function_test(self, func: FunctionInfo) -> str:
        """Genera test para una funcion standalone."""
        arrange = self._generate_arrange(func)
        self._generate_act(func)
        assertions = self._generate_assertions(func)
        edge_cases = self._generate_edge_cases(func)

        async_prefix = "async " if func.is_async else ""
        await_prefix = "await " if func.is_async else ""

        return f'''
{async_prefix}def test_{func.name}_basic():
    """Test basico para {func.name}."""
    # Arrange
    {arrange}

    # Act
    result = {await_prefix}{func.name}({", ".join(func.args)})

    # Assert
    {assertions}


{async_prefix}def test_{func.name}_edge_cases():
    """Test de casos limite para {func.name}."""
{edge_cases}


@pytest.mark.parametrize("input_val,expected", [
    (None, None),
])
{async_prefix}def test_{func.name}_parametrized(input_val, expected):
    """Test parametrizado para {func.name}."""
    result = {await_prefix}{func.name}(input_val)
    assert result == expected
'''

    def _generate_class_tests(self, class_name: str, methods: list[FunctionInfo]) -> str:
        """Genera tests para una clase."""
        test_methods = []

        for method in methods:
            test_methods.append(self._generate_method_test(method))

        return f'''
class Test{class_name}:
    """Tests para {class_name}."""

    @pytest.fixture
    def instance(self):
        """Crea instancia para tests."""
        return {class_name}()

    @pytest.fixture
    def mock_dependencies(self):
        """Mock de dependencias."""
        return {{
            # Agregar: mocks necesarios
        }}

{"".join(test_methods)}
'''

    def _generate_method_test(self, func: FunctionInfo) -> str:
        """Genera test para un metodo de clase."""
        arrange = self._generate_arrange(func)
        assertions = self._generate_assertions(func)
        failure_test = self._generate_failure_test(func)

        async_prefix = "async " if func.is_async else ""
        await_prefix = "await " if func.is_async else ""

        args_str = ", ".join(func.args) if func.args else ""

        return f'''
    {async_prefix}def test_{func.name}_success(self, instance):
        """Test exitoso de {func.name}."""
        # Arrange
        {arrange}

        # Act
        result = {await_prefix}instance.{func.name}({args_str})

        # Assert
        {assertions}

    {async_prefix}def test_{func.name}_failure(self, instance):
        """Test de fallo de {func.name}."""
{failure_test}
'''

    def _generate_edge_cases(self, func: FunctionInfo) -> str:
        """Genera tests de casos limite para una funcion."""
        if not func.args:
            return (
                "    # Sin parametros: verificar idempotencia\n"
                "    result1 = {call}\n"
                "    result2 = {call}\n"
                "    assert result1 == result2"
            ).format(call=(f"{'await ' if func.is_async else ''}{func.name}()"))

        lines = []
        for arg in func.args:
            arg_lower = arg.lower()
            call_args = ", ".join(
                "None" if a == arg else self._default_value_for(a) for a in func.args
            )
            call = f"{'await ' if func.is_async else ''}{func.name}({call_args})"

            # Test con None
            lines.append(f"    # Caso: {arg}=None")
            lines.append("    try:")
            lines.append(f"        result = {call}")
            lines.append("    except (TypeError, ValueError):")
            lines.append("        pass  # Excepcion esperada con None")
            lines.append("")

            # Tests especificos segun nombre del parametro
            if "str" in arg_lower or "name" in arg_lower or "text" in arg_lower:
                empty_args = ", ".join(
                    '""' if a == arg else self._default_value_for(a) for a in func.args
                )
                empty_call = f"{'await ' if func.is_async else ''}{func.name}({empty_args})"
                lines.append(f"    # Caso: {arg} vacio")
                lines.append(f"    result = {empty_call}")
                lines.append("    assert result is not None")
                lines.append("")

            elif "list" in arg_lower or "items" in arg_lower:
                empty_args = ", ".join(
                    "[]" if a == arg else self._default_value_for(a) for a in func.args
                )
                empty_call = f"{'await ' if func.is_async else ''}{func.name}({empty_args})"
                lines.append(f"    # Caso: {arg} lista vacia")
                lines.append(f"    result = {empty_call}")
                lines.append("    assert result is not None")
                lines.append("")

            elif "id" in arg_lower:
                neg_args = ", ".join(
                    "-1" if a == arg else self._default_value_for(a) for a in func.args
                )
                zero_args = ", ".join(
                    "0" if a == arg else self._default_value_for(a) for a in func.args
                )
                neg_call = f"{'await ' if func.is_async else ''}{func.name}({neg_args})"
                zero_call = f"{'await ' if func.is_async else ''}{func.name}({zero_args})"
                lines.append(f"    # Caso: {arg} negativo")
                lines.append("    try:")
                lines.append(f"        result = {neg_call}")
                lines.append("    except (ValueError, KeyError):")
                lines.append("        pass  # Excepcion esperada con ID negativo")
                lines.append("")
                lines.append(f"    # Caso: {arg} cero")
                lines.append("    try:")
                lines.append(f"        result = {zero_call}")
                lines.append("    except (ValueError, KeyError):")
                lines.append("        pass  # Excepcion esperada con ID cero")
                lines.append("")

        return "\n".join(lines).rstrip()

    def _generate_failure_test(self, func: FunctionInfo) -> str:
        """Genera test de fallo para un metodo de clase."""
        lines = []

        if func.args:
            # Test con argumentos invalidos (None para todos)
            none_args = ", ".join("None" for _ in func.args)
            call = f"{'await ' if func.is_async else ''}instance.{func.name}({none_args})"
            lines.append("        # Verificar manejo de argumentos invalidos")
            lines.append("        with pytest.raises((TypeError, ValueError, AttributeError)):")
            lines.append(f"            {call}")
        else:
            # Sin args: patch para provocar fallo interno
            lines.append("        # Verificar manejo de estado invalido")
            lines.append('        with patch.object(instance, "__dict__", {}):')
            call = f"{'await ' if func.is_async else ''}instance.{func.name}()"
            lines.append("            try:")
            lines.append(f"                {call}")
            lines.append("            except Exception:")
            lines.append("                pass  # El metodo deberia manejar estado invalido")

        return "\n".join(lines)

    def _default_value_for(self, arg: str) -> str:
        """Retorna un valor por defecto apropiado segun el nombre del argumento."""
        arg_lower = arg.lower()
        if "id" in arg_lower:
            return "1"
        elif "name" in arg_lower or "str" in arg_lower or "text" in arg_lower:
            return f'"test_{arg}"'
        elif "list" in arg_lower or "items" in arg_lower:
            return "[]"
        elif "dict" in arg_lower or "data" in arg_lower:
            return "{}"
        elif "bool" in arg_lower or arg.startswith("is_"):
            return "True"
        else:
            return "Mock()"

    def _generate_arrange(self, func: FunctionInfo) -> str:
        """Genera sección Arrange."""
        if not func.args:
            return "# Sin parámetros"

        lines = []
        for arg in func.args:
            # Intentar inferir tipo del nombre
            if "id" in arg.lower():
                lines.append(f"{arg} = 1")
            elif "name" in arg.lower() or "str" in arg.lower():
                lines.append(f'{arg} = "test_{arg}"')
            elif "list" in arg.lower() or "items" in arg.lower():
                lines.append(f"{arg} = []")
            elif "dict" in arg.lower() or "data" in arg.lower():
                lines.append(f"{arg} = {{}}")
            elif "bool" in arg.lower() or arg.startswith("is_"):
                lines.append(f"{arg} = True")
            else:
                lines.append(f"{arg} = Mock()")

        return "\n    ".join(lines)

    def _generate_act(self, func: FunctionInfo) -> str:
        """Genera sección Act."""
        args = ", ".join(func.args)
        if func.is_async:
            return f"result = await {func.name}({args})"
        return f"result = {func.name}({args})"

    def _generate_assertions(self, func: FunctionInfo) -> str:
        """Genera assertions básicos."""
        assertions = ["assert result is not None"]

        if func.returns:
            if "list" in func.returns.lower():
                assertions.append("assert isinstance(result, list)")
            elif "dict" in func.returns.lower():
                assertions.append("assert isinstance(result, dict)")
            elif "str" in func.returns.lower():
                assertions.append("assert isinstance(result, str)")
            elif "int" in func.returns.lower():
                assertions.append("assert isinstance(result, int)")
            elif "bool" in func.returns.lower():
                assertions.append("assert isinstance(result, bool)")

        return "\n    ".join(assertions)


def generate_tests_for_file(
    source_path: Path, output_path: Path, framework: str = "pytest"
) -> None:
    """Genera tests para un archivo de código."""
    logger.info(f"Procesando: {source_path}")

    source_code = source_path.read_text(encoding="utf-8")
    analyzer = CodeAnalyzer(source_code)

    if not analyzer.functions:
        logger.warning(f"No se encontraron funciones en {source_path}")
        return

    logger.info(f"Encontradas {len(analyzer.functions)} funciones")

    generator = TestGenerator(framework=framework)
    module_name = source_path.stem

    test_code = generator.generate_tests(analyzer.functions, module_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(test_code, encoding="utf-8")

    logger.info(f"Tests generados: {output_path}")


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Genera tests automáticamente basados en código fuente.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python test_generator.py --file src/module.py --output tests/test_module.py
    python test_generator.py --dir src/ --output-dir tests/
    python test_generator.py --file src/api.py --framework pytest
        """,
    )

    parser.add_argument("--file", "-f", type=Path, help="Archivo Python a analizar")
    parser.add_argument("--dir", "-d", type=Path, help="Directorio de archivos a analizar")
    parser.add_argument("--output", "-o", type=Path, help="Archivo de salida para tests")
    parser.add_argument("--output-dir", type=Path, help="Directorio de salida para tests")
    parser.add_argument(
        "--framework",
        choices=["pytest", "unittest"],
        default="pytest",
        help="Framework de testing (default: pytest)",
    )
    parser.add_argument(
        "--style", choices=["aaa", "gherkin"], default="aaa", help="Estilo de tests (default: aaa)"
    )

    args = parser.parse_args()

    if args.file:
        if not args.file.exists():
            logger.error(f"Archivo no encontrado: {args.file}")
            sys.exit(1)

        output = args.output or Path(f"tests/test_{args.file.stem}.py")
        generate_tests_for_file(args.file, output, args.framework)

    elif args.dir:
        if not args.dir.exists():
            logger.error(f"Directorio no encontrado: {args.dir}")
            sys.exit(1)

        output_dir = args.output_dir or Path("tests")

        for py_file in args.dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            relative = py_file.relative_to(args.dir)
            output = output_dir / f"test_{relative}"
            generate_tests_for_file(py_file, output, args.framework)

    else:
        parser.print_help()
        sys.exit(1)

    logger.info("Generación completada")


if __name__ == "__main__":
    main()
