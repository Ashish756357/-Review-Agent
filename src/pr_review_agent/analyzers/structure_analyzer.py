"""
Structure and standards analyzer.

Performs lightweight AST-based checks for Python files to provide
feedback on code structure, style patterns, and common bug-prone usages.
This analyzer is intentionally self-contained and pure-Python so it can
run on file content strings without relying on external CLI tools.
"""
from typing import Dict, List, Any
import ast

from .base import StyleAnalyzerBase, AnalysisResult


class StructureAnalyzer(StyleAnalyzerBase):
    """Analyzer that inspects Python AST for structural issues.

    Checks implemented:
    - Mutable default arguments
    - Bare except clauses
    - Use of eval/exec
    - Too many function arguments
    - Deep nesting
    - Use of print statements (likely debugging)
    - Shadowing of builtins
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.category = "structure"

    def get_supported_extensions(self) -> List[str]:
        return [".py"]

    async def analyze(self, file_path: str, content: str, **kwargs) -> List[AnalysisResult]:
        results: List[AnalysisResult] = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            results.append(AnalysisResult(
                file_path=file_path,
                line=e.lineno,
                severity="error",
                category=self.category,
                message=f"Syntax error: {e.msg}",
                suggestion="Fix the syntax error reported by the parser.",
                confidence=0.9
            ))
            return results

        # helper: detect maximum nesting depth
        class NestingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.max_depth = 0
                self._depth = 0

            def generic_visit(self, node):
                self._depth += 1
                if self._depth > self.max_depth:
                    self.max_depth = self._depth
                super().generic_visit(node)
                self._depth -= 1

        # collect function arg counts, mutable defaults, bare excepts, eval usage, print calls, shadowing
        builtin_names = set(dir(__builtins__))
        assigned_names = set()

        for node in ast.walk(tree):
            # assignments for shadow detection
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                else:
                    targets = [node.target]

                for t in targets:
                    if isinstance(t, ast.Name):
                        assigned_names.add(t.id)

            # Function definitions
            if isinstance(node, ast.FunctionDef):
                arg_count = len(node.args.args) + len(node.args.kwonlyargs)
                if node.args.vararg:
                    arg_count += 1
                if node.args.kwarg:
                    arg_count += 1

                if arg_count > 6:
                    results.append(AnalysisResult(
                        file_path=file_path,
                        line=node.lineno,
                        severity="warning",
                        category=self.category,
                        message=f"Function '{node.name}' has many parameters ({arg_count}). Consider refactoring.",
                        suggestion="Reduce the number of parameters (use objects or kwargs) or split the function.",
                        confidence=0.6
                    ))

                # mutable default args
                if node.args.defaults:
                    for idx, default in enumerate(node.args.defaults):
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            results.append(AnalysisResult(
                                file_path=file_path,
                                line=node.lineno,
                                severity="warning",
                                category=self.category,
                                message=f"Function '{node.name}' uses a mutable default argument.",
                                suggestion="Use None as the default and create the mutable object inside the function.",
                                confidence=0.8
                            ))

            # Bare except handlers
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    results.append(AnalysisResult(
                        file_path=file_path,
                        line=node.lineno,
                        severity="warning",
                        category=self.category,
                        message="Bare except clause detected.",
                        suggestion="Catch specific exceptions instead of using a bare 'except:'.",
                        confidence=0.7
                    ))

            # eval/exec usage
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec"):
                    results.append(AnalysisResult(
                        file_path=file_path,
                        line=node.lineno,
                        severity="error",
                        category=self.category,
                        message=f"Use of '{node.func.id}' detected — this can be unsafe.",
                        suggestion="Avoid eval/exec or sanitize inputs carefully.",
                        confidence=0.9
                    ))

            # print statements (likely debugging left behind)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                results.append(AnalysisResult(
                    file_path=file_path,
                    line=node.lineno,
                    severity="info",
                    category=self.category,
                    message="Use of 'print' detected — consider using logging for production code.",
                    suggestion="Replace print() with logging calls and appropriate log levels.",
                    confidence=0.5
                ))

        # shadowing builtins
        shadowed = assigned_names.intersection(builtin_names)
        for name in shadowed:
            results.append(AnalysisResult(
                file_path=file_path,
                severity="warning",
                category=self.category,
                message=f"Name '{name}' shadows a Python builtin.",
                suggestion="Rename the variable to avoid shadowing builtins.",
                confidence=0.6
            ))

        # nesting depth check
        nv = NestingVisitor()
        nv.visit(tree)
        if nv.max_depth > 8:
            results.append(AnalysisResult(
                file_path=file_path,
                severity="warning",
                category=self.category,
                message=f"High nesting depth ({nv.max_depth}). Consider simplifying control flow.",
                suggestion="Refactor deeply nested code into smaller functions or early returns.",
                confidence=0.6
            ))

        return results
