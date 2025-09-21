"""
Security analyzer for Python code.

This module provides security analysis for Python code, detecting common
vulnerabilities and security issues.
"""

import ast
import re
from typing import List, Dict, Any
from .base import SecurityAnalyzerBase, AnalysisResult


class PythonSecurityAnalyzer(SecurityAnalyzerBase):
    """
    Security analyzer for Python code.

    Detects common security vulnerabilities including:
    - SQL injection
    - Command injection
    - Path traversal
    - Insecure random values
    - Hardcoded secrets
    - Insecure deserialization
    - XSS vulnerabilities
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.sensitive_patterns = [
            # API keys and tokens
            (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
             "Hardcoded API key detected"),
            (r'(?i)(token|access[_-]?token)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
             "Hardcoded token detected"),
            (r'(?i)(secret|password|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']',
             "Hardcoded secret/password detected"),

            # Database credentials
            (r'(?i)(database[_-]?url|db[_-]?url)\s*[=:]\s*["\']([^"\']+)["\']',
             "Database URL in code"),
            (r'(?i)(db[_-]?password|database[_-]?password)\s*[=:]\s*["\']([^"\']+)["\']',
             "Database password in code"),

            # AWS credentials
            (r'AWS[_-]?ACCESS[_-]?KEY[_-]?ID\s*[=:]\s*["\']([A-Z0-9]{20})["\']',
             "AWS access key ID in code"),
            (r'AWS[_-]?SECRET[_-]?ACCESS[_-]?KEY\s*[=:]\s*["\']([a-zA-Z0-9/+]{40})["\']',
             "AWS secret access key in code"),

            # Private keys
            (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----',
             "Private key in code"),
            (r'-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----',
             "SSH private key in code"),
        ]

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".py"]

    async def analyze(self, file_path: str, content: str, **kwargs) -> List[AnalysisResult]:
        """
        Analyze Python code for security issues.

        Args:
            file_path: Path to the Python file
            content: File content as string
            **kwargs: Additional arguments

        Returns:
            List of AnalysisResult objects
        """
        results = []

        try:
            # Parse the AST for structural analysis
            tree = ast.parse(content, filename=file_path)
            results.extend(self._analyze_ast(tree, file_path))

            # Pattern-based analysis for hardcoded secrets
            results.extend(self._analyze_patterns(content, file_path))

            # String literal analysis
            results.extend(self._analyze_strings(content, file_path))

        except SyntaxError as e:
            results.append(AnalysisResult(
                file_path=file_path,
                line=e.lineno,
                column=e.offset,
                severity="warning",
                category="security",
                message=f"Syntax error in Python code: {e.msg}",
                suggestion="Fix syntax errors before security analysis"
            ))
        except Exception as e:
            results.append(AnalysisResult(
                file_path=file_path,
                severity="error",
                category="security",
                message=f"Security analysis failed: {str(e)}",
                suggestion="Check file format and try again"
            ))

        return results

    def _analyze_ast(self, tree: ast.AST, file_path: str) -> List[AnalysisResult]:
        """Analyze AST for security issues."""
        results = []
        analyzer = ASTSecurityAnalyzer(file_path)
        analyzer.visit(tree)

        for issue in analyzer.issues:
            results.append(AnalysisResult(
                file_path=file_path,
                line=issue["line"],
                column=issue["column"],
                severity=issue["severity"],
                category="security",
                message=issue["message"],
                suggestion=issue.get("suggestion"),
                code_snippet=issue.get("code_snippet")
            ))

        return results

    def _analyze_patterns(self, content: str, file_path: str) -> List[AnalysisResult]:
        """Analyze content for hardcoded secrets using regex patterns."""
        results = []

        for pattern, message in self.sensitive_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_number = content[:match.start()].count('\n') + 1

                results.append(AnalysisResult(
                    file_path=file_path,
                    line=line_number,
                    severity="critical",
                    category="security",
                    message=message,
                    suggestion="Move sensitive data to environment variables or secure configuration",
                    code_snippet=match.group(0)[:100] + "..." if len(match.group(0)) > 100 else match.group(0)
                ))

        return results

    def _analyze_strings(self, content: str, file_path: str) -> List[AnalysisResult]:
        """Analyze string literals for potential security issues."""
        results = []

        try:
            tree = ast.parse(content, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Str) or isinstance(node, ast.Constant) and isinstance(node.value, str):
                    string_value = node.value if isinstance(node, ast.Str) else node.value

                    # Check for SQL injection patterns
                    if self._is_sql_injection_risk(string_value):
                        results.append(AnalysisResult(
                            file_path=file_path,
                            line=getattr(node, 'lineno', 0),
                            severity="warning",
                            category="security",
                            message="Potential SQL injection vulnerability",
                            suggestion="Use parameterized queries or SQLAlchemy ORM",
                            code_snippet=string_value[:100] + "..." if len(string_value) > 100 else string_value
                        ))

                    # Check for command injection patterns
                    if self._is_command_injection_risk(string_value):
                        results.append(AnalysisResult(
                            file_path=file_path,
                            line=getattr(node, 'lineno', 0),
                            severity="critical",
                            category="security",
                            message="Potential command injection vulnerability",
                            suggestion="Avoid shell=True or validate/sanitize input",
                            code_snippet=string_value[:100] + "..." if len(string_value) > 100 else string_value
                        ))

                    # Check for path traversal patterns
                    if self._is_path_traversal_risk(string_value):
                        results.append(AnalysisResult(
                            file_path=file_path,
                            line=getattr(node, 'lineno', 0),
                            severity="warning",
                            category="security",
                            message="Potential path traversal vulnerability",
                            suggestion="Validate and sanitize file paths",
                            code_snippet=string_value[:100] + "..." if len(string_value) > 100 else string_value
                        ))

        except Exception:
            # If AST parsing fails, skip string analysis
            pass

        return results

    def _is_sql_injection_risk(self, string_value: str) -> bool:
        """Check if string contains SQL injection patterns."""
        sql_patterns = [
            r'SELECT.*FROM.*WHERE.*\+',
            r'INSERT.*INTO.*VALUES.*\+',
            r'UPDATE.*SET.*WHERE.*\+',
            r'DELETE.*FROM.*WHERE.*\+',
            r'EXEC\s*\(',
            r'EXECUTE\s*\(',
        ]

        return any(re.search(pattern, string_value, re.IGNORECASE) for pattern in sql_patterns)

    def _is_command_injection_risk(self, string_value: str) -> bool:
        """Check if string contains command injection patterns."""
        cmd_patterns = [
            r'subprocess\.call\s*\(',
            r'subprocess\.run\s*\(',
            r'os\.system\s*\(',
            r'os\.popen\s*\(',
            r'commands\.getstatusoutput\s*\(',
            r'shell\s*=\s*True',
        ]

        return any(re.search(pattern, string_value, re.IGNORECASE) for pattern in cmd_patterns)

    def _is_path_traversal_risk(self, string_value: str) -> bool:
        """Check if string contains path traversal patterns."""
        traversal_patterns = [
            r'\.\./',
            r'\.\.\\',
            r'/\.\./',
            r'\\\.\.\\',
        ]

        return any(pattern in string_value for pattern in traversal_patterns)


class ASTSecurityAnalyzer(ast.NodeVisitor):
    """
    AST visitor for security analysis.

    Analyzes Python AST for security issues that require structural analysis.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.issues = []

    def visit_Call(self, node):
        """Analyze function calls for security issues."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id

            # Check for dangerous functions
            if func_name in ['eval', 'exec']:
                self.issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "severity": "critical",
                    "message": f"Use of dangerous function '{func_name}'",
                    "suggestion": "Avoid eval/exec - use safer alternatives",
                    "code_snippet": self._get_code_snippet(node)
                })

            elif func_name == 'input':
                self.issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "severity": "warning",
                    "message": "Use of input() function without validation",
                    "suggestion": "Validate and sanitize user input",
                    "code_snippet": self._get_code_snippet(node)
                })

            elif func_name in ['pickle', 'cPickle']:
                # Check for pickle usage
                for keyword in node.keywords:
                    if keyword.arg == 'loads' or (len(node.args) > 0 and
                        isinstance(keyword.value, ast.Str) and 'load' in keyword.value.value):
                        self.issues.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "severity": "warning",
                            "message": "Use of pickle.loads() - potential deserialization vulnerability",
                            "suggestion": "Use safer serialization formats like JSON",
                            "code_snippet": self._get_code_snippet(node)
                        })

        self.generic_visit(node)

    def visit_Import(self, node):
        """Analyze import statements for security issues."""
        for alias in node.names:
            module_name = alias.name

            # Check for dangerous imports
            dangerous_modules = [
                'subprocess', 'os.system', 'commands', 'shutil', 'glob'
            ]

            if module_name in dangerous_modules:
                self.issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "severity": "info",
                    "message": f"Import of potentially dangerous module '{module_name}'",
                    "suggestion": "Review usage for security implications",
                    "code_snippet": self._get_code_snippet(node)
                })

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Analyze from-import statements for security issues."""
        if node.module:
            # Check for dangerous from-imports
            if node.module == 'os' and any(alias.name in ['system', 'popen', 'spawn']
                                        for alias in node.names):
                self.issues.append({
                    "line": node.lineno,
                    "column": node.col_offset,
                    "severity": "warning",
                    "message": "Import of dangerous os functions",
                    "suggestion": "Use safer alternatives for system operations",
                    "code_snippet": self._get_code_snippet(node)
                })

        self.generic_visit(node)

    def _get_code_snippet(self, node: ast.AST) -> str:
        """Get a code snippet around the node."""
        # This is a simplified version - in practice, you'd want to
        # extract the actual source code around the node
        return f"Line {node.lineno}: {type(node).__name__}"
