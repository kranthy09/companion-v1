# project/api/mcp_indexer.py
import re
from pathlib import Path
from typing import Dict, List, Set
from functools import lru_cache


class FrontendIndexer:
    def __init__(self, frontend_path: str = "../companion-frontend/src"):
        self.path = Path(frontend_path)

    @lru_cache(maxsize=1)
    def build_index(self) -> Dict:
        """Build complete frontend index - cached"""
        return {
            "components": self._index_components(),
            "api_usage": self._index_api_usage(),
            "routes": self._index_routes(),
            "hooks": self._index_hooks(),
            "stores": self._index_stores()
        }

    def _index_components(self) -> List[Dict]:
        """Index all components with metadata"""
        components = []

        for file in self.path.rglob("*.tsx"):
            if "node_modules" in str(file):
                continue

            content = file.read_text(encoding='utf-8')

            # Extract component info
            component_match = re.search(
                r'(?:export\s+(?:default\s+)?function|const)\s+(\w+)',
                content
            )

            if component_match:
                components.append({
                    "name": component_match.group(1),
                    "path": str(file.relative_to(self.path)),
                    "type": self._get_component_type(file),
                    "imports": self._extract_imports(content),
                    "api_calls": self._extract_api_calls(content),
                    "hooks_used": self._extract_hooks(content)
                })

        return components

    def _index_api_usage(self) -> List[Dict]:
        """Map API calls to components"""
        usage = []

        for file in self.path.rglob("*.ts*"):
            if "node_modules" in str(file):
                continue

            content = file.read_text(encoding='utf-8')
            api_calls = self._extract_api_calls(content)

            if api_calls:
                usage.append({
                    "file": str(file.relative_to(self.path)),
                    "apis": list(api_calls)
                })

        return usage

    def _index_routes(self) -> List[Dict]:
        """Index Next.js app router pages"""
        routes = []

        app_dir = self.path / "app"
        if not app_dir.exists():
            return routes

        for page in app_dir.rglob("page.tsx"):
            route_path = str(page.parent.relative_to(app_dir))
            route_path = "/" + route_path.replace("\\", "/")

            content = page.read_text(encoding='utf-8')

            routes.append({
                "path": route_path,
                "file": str(page.relative_to(self.path)),
                "api_calls": list(self._extract_api_calls(content))
            })

        return routes

    def _index_hooks(self) -> List[Dict]:
        """Index custom hooks"""
        hooks = []

        hooks_dir = self.path / "hooks"
        if not hooks_dir.exists():
            return hooks

        for file in hooks_dir.rglob("*.ts"):
            content = file.read_text(encoding='utf-8')

            hook_match = re.search(
                r'export\s+(?:function|const)\s+(use\w+)', content)
            if hook_match:
                hooks.append({
                    "name": hook_match.group(1),
                    "path": str(file.relative_to(self.path)),
                    "api_calls": list(self._extract_api_calls(content))
                })

        return hooks

    def _index_stores(self) -> List[Dict]:
        """Index Zustand stores"""
        stores = []

        stores_dir = self.path / "stores"
        if not stores_dir.exists():
            return stores

        for file in stores_dir.rglob("*.ts"):
            content = file.read_text(encoding='utf-8')

            store_match = re.search(r'create\s*\(\s*\(', content)
            if store_match:
                stores.append({
                    "name": file.stem,
                    "path": str(file.relative_to(self.path)),
                    "api_calls": list(self._extract_api_calls(content))
                })

        return stores

    def _get_component_type(self, file: Path) -> str:
        """Determine component type from path"""
        path_str = str(file)
        if "/components/ui/" in path_str:
            return "ui"
        elif "/components/features/" in path_str:
            return "feature"
        elif "/components/layout/" in path_str:
            return "layout"
        elif "/app/" in path_str:
            return "page"
        return "component"

    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements"""
        imports = re.findall(
            r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]', content)
        return [imp for imp in imports if not imp.startswith('.')][:5]

    def _extract_api_calls(self, content: str) -> Set[str]:
        """Extract api.* calls"""
        calls = set()

        # Match: api.blog.create, api.notes.list, etc.
        matches = re.findall(r'api\.(\w+)\.(\w+)', content)
        for namespace, method in matches:
            calls.add(f"{namespace}.{method}")

        return calls

    def _extract_hooks(self, content: str) -> List[str]:
        """Extract hook usage"""
        hooks = []

        patterns = [
            r'(use\w+)\s*\(',
            r'const\s+.*\s*=\s*(use\w+)\s*\('
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            hooks.extend(matches)

        return list(set(hooks))[:5]

    def search_api_usage(self, api_namespace: str) -> List[Dict]:
        """Search for specific API usage"""
        index = self.build_index()
        results = []

        for item in index["api_usage"]:
            matching_apis = [
                api for api in item["apis"]
                if api.startswith(api_namespace)
            ]
            if matching_apis:
                results.append({
                    "file": item["file"],
                    "apis": matching_apis
                })

        return results

    def get_component_details(self, component_name: str) -> Dict:
        """Get detailed info about a component"""
        index = self.build_index()

        for comp in index["components"]:
            if component_name.lower() in comp["name"].lower():
                return comp

        return {"error": "Component not found"}


# Singleton instance
_indexer = None


def get_indexer() -> FrontendIndexer:
    global _indexer
    if _indexer is None:
        _indexer = FrontendIndexer()
    return _indexer
