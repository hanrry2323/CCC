# Plan: tmpl-html-scene — HTML 场景模板核心系统：Registry + 变量插值引擎 + 校验

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

### 关键发现（影响执行方案的代码现状）

- **`src/xianyu/html_scene/templates/__init__.py:10-21`** — 已有 `load_template()` 和 `list_templates()` 两个函数，但极其简陋：只做文件 I/O，无缓存、无元数据、无发现逻辑、无外部路径支持。`list_templates()` 通过 `glob("*.html")` 扫描目录，排除了 `__init__` 但不会过滤非模板 HTML 文件
- **`src/xianyu/html_scene/agent.py:20-43`** — Jinja2 渲染硬编码在 module 级别的 `_JINJA_ENV` 中，只加载 `templates/` 目录。`render_scene_html()` 第 139-149 行有 6 个硬编码变量（`scene_title`, `scene_subtitle`, `scene_content`, `scene_index`, `total_scenes`, `duration`），无变量 schema、无校验、无类型检查。新增模板无法声明自定义变量
- **`src/xianyu/html_scene/schema.py:10-36`** — 仅有 `SceneStyle` 枚举 + `SceneDescription`/`SceneScript` Pydantic 模型，完全不含模板元数据、变量定义或模板校验相关类型
- **所有 7 个 `.html` 模板**（`minimal/tech/story/cinematic/vibrant/elegant/dark`）使用相同的 4 个变量：`scene_title`, `scene_subtitle`, `scene_content`, `scene_index`, `total_scenes`。`scene_subtitle` 全部经 `{% if scene_subtitle %}` 保护。变量全部通过 `{{ }}` 表达式引用，无 `{% set %}` 或 `{% macro %}` 等复杂构造
- **`tests/html_scene/test_agent.py`** — 现有测试覆盖 `render_scene_html()` / `generate_all_html()` / `ab_compare_templates()`，但全部使用硬编码的 6 个变量，无变量 schema/registry 相关测试
- **没有模板校验系统** — 当前没有任何代码检查模板的 HTML 结构完整性、DOMParser 校验、CSS 语法检查或渲染一致性

### 待改动点
- `src/xianyu/html_scene/registry.py`（新建）— TemplateRegistry：元数据模型 + 模板发现 + 注册 + 缓存
- `src/xianyu/html_scene/interpolation.py`（新建）— 变量插值引擎 + 变量 schema 定义 + 类型校验 + 默认值 + 渲染 wrapper
- `src/xianyu/html_scene/validation.py`（新建）— 模板校验：HTML 结构、变量一致性、元数据校验
- `src/xianyu/html_scene/schema.py` — 追加 `TemplateMeta`/`VariableDef` 模型（在已有 SceneStyle/SceneDescription 基础上新增，不改现有模型）
- `src/xianyu/html_scene/templates/__init__.py` — 保留 `load_template()`/`list_templates()` 作向后兼容，函数体委托给 registry，不做大改
- `src/xianyu/html_scene/agent.py` — `render_scene_html()` 新增可选 schema-aware 分支（通过 registry+interpolation 替换硬编码 `_JINJA_ENV.render()`）
- `tests/html_scene/test_registry.py`（新建）
- `tests/html_scene/test_interpolation.py`（新建）
- `tests/html_scene/test_validation.py`（新建）

---

## 范围

- **目标**：构建 HTML 场景模板核心系统 — 三组件（Registry + 插值引擎 + 校验），覆盖模板从注册到渲染的完整生命周期
- **只改文件**：
  - `src/xianyu/html_scene/registry.py`（新建）
  - `src/xianyu/html_scene/interpolation.py`（新建）
  - `src/xianyu/html_scene/validation.py`（新建）
  - `src/xianyu/html_scene/schema.py`
  - `src/xianyu/html_scene/agent.py`
  - `src/xianyu/html_scene/__init__.py`
  - `tests/html_scene/test_registry.py`（新建）
  - `tests/html_scene/test_interpolation.py`（新建）
  - `tests/html_scene/test_validation.py`（新建）
- **不改文件**：`templates/__init__.py`（委托不改）、`renderer.py`（Playwright 渲染入口不变）、`templates/*.html`（模板本身不动，只是新增 registry 消费它们）、`scene.py`（video scene 模型与 html_scene 无关）
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1/1）：HTML 场景模板核心系统 — Registry + 变量插值引擎 + 校验

### 做什么

构建三组件系统，解决当前模板系统的三个核心缺失：

**1. TemplateRegistry（注册表）**
当前模板通过 `templates/__init__.py` 的 `load_template()` 文件 I/O 直接访问，无缓存、无元数据、无外部路径发现。TemplateRegistry 提供：
- `TemplateMeta` dataclass：每套模板的名称、风格、版本、变量声明列表、标签、作者、描述
- `VariableDef` dataclass：每个变量的名字、类型、是否必填、默认值、描述
- `TemplateInfo` dataclass：运行时模板对象（元数据 + 原始内容 + AST 缓存 + 来源标记）
- `TemplateRegistry` 类：内置模板目录自动发现（`discover()`）+ 外部路径注册（`add_path()`）+ 单模板注册（`register()`）+ 按名称/风格查询（`get_template()`/`list_templates()`）+ 缓存
- 内置 7 个模板在首次注册时**自动提取变量引用**（通过 `interpolation.extract_variable_refs()`），自动生成 `VariableDef`（全部标记 `required=False`、类型为 `str`、描述自动生成）
- 用户可通过注册带 `TemplateMeta` 的模板来覆盖变量声明（添加必填校验、类型约束、默认值）

**2. InterpolationEngine（变量插值引擎）**
当前 `agent.py` 的 `render_scene_html()` 硬编码 6 个变量传给 Jinja2。InterpolationEngine 是一个 schema-aware 封装层：
- `render(template_content, variables)` — 渲染前校验：
  - 所有 `required=True` 的变量已提供（缺失 → `ValueError`）
  - 提供变量的类型与声明匹配（类型转换或报错）
  - 未声明的变量注入警告（不阻塞渲染，仅 log warning）
  - 可选变量自动填充默认值
  - 过滤掉未在 schema 中声明的变量（防止模板意外访问未注册变量）
- `extract_variable_refs(template_content)` — 通过 Jinja2 AST 解析器提取所有 `{{ var }}` 和 `{% if var %}` 中引用的变量名集合，不依赖正则
- 纯函数设计：无全局状态，输入 template + variables → 输出 HTML
- 签名：`class InterpolationEngine` + `render()` 实例方法

**3. Validation（模板校验系统）**
当前没有任何模板校验。Validation 提供三层次校验：
- **变量校验**：对比模板中实际引用的变量 vs 声明的变量列表，报告未声明引用和未在模板中使用的声明
- **HTML 结构校验**：DOMParser 检查标签闭合、DOCTYPE 声明、`<html>`/`<head>`/`<body>` 结构完整性
- **渲染校验**：用 sample 变量渲染模板，验证不抛异常、输出含预期变量值
- `ValidationResult` dataclass：携带 `errors`、`warnings`、`info` 三份列表，每项有 `message` + `location`（行号/列号）
- 返回 `ValidationResult` 而非抛异常，便于批量处理

**系统集成**：
- `schema.py` 新增 `TemplateMeta`/`VariableDef` Pydantic 模型
- `agent.py` 的 `render_scene_html()` 新增可选 `registry` 参数：传入时走 schema-aware 渲染，不传时保持向后兼容的硬编码渲染
- `__init__.py` 导出新增 3 模块的所有公开接口

**预期效果**：
- `registry = TemplateRegistry()` → `registry.discover()` 自动识别 7 个内置模板，提取变量引用，缓存元数据
- `engine = InterpolationEngine()` → `engine.render(content, variables, schema)` 校验变量后渲染
- `validate_template(content, meta)` → 返回 `ValidationResult`（errors + warnings + info）
- 现有 `render_scene_html()` 不传 registry 参数 → 行为完全不变，零回归
- 外部代码可 `registry.register("my_template", html_str, meta=TemplateMeta(...))` 动态添加模板

### 怎么做

**基准前提**：所有 7 个现有 HTML 模板使用纯 Jinja2 `{{ }}` 变量引用（无 `{% set %}` / `{% macro %}` / `{% call %}` 等复杂构造），`scene_subtitle` 经 `{% if %}` 保护。`extract_variable_refs()` 通过 jinja2.meta.find_undeclared_variables() + 额外扫描 `{% %}` 中的条件变量完整覆盖。

**1. `src/xianyu/html_scene/schema.py` — 追加数据模型**

在现有 `SceneStyle` / `SceneDescription` / `SceneScript` 之后追加（不改动现有模型）：

```python
# ── 模板元数据模型（tmpl-html-scene 新增） ──

from enum import StrEnum as _StrEnum
from typing import Any


class VariableType(str, _StrEnum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"


class VariableDef(BaseModel):
    """单个模板变量的定义。

    Attributes:
        name: 变量名（在模板中通过 {{ name }} 引用）。
        type: 变量类型，str/int/float/bool。
        description: 变量用途说明。
        required: 是否必填。False 时使用 default 值。
        default: 默认值（required=False 时生效，None = 显式空值）。
    """
    name: str = Field(..., min_length=1)
    type: VariableType = Field(default=VariableType.STR)
    description: str = Field(default="")
    required: bool = Field(default=False)
    default: Any = Field(default=None)


class TemplateMeta(BaseModel):
    """HTML 场景模板的元数据。

    Attributes:
        name: 模板标识名（如 "minimal", "tech"），对应 templates/<name>.html。
        description: 模板说明。
        style: 关联的 SceneStyle 枚举（用于分类/筛选）。
        version: 模板版本号（语义化）。
        author: 模板作者。
        variables: 变量定义列表。空列表 = 允许任意变量（宽松模式）。
        tags: 标签列表，用于分类搜索。
    """
    name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str = Field(default="")
    style: SceneStyle = Field(default=SceneStyle.MINIMAL)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    author: str = Field(default="built-in")
    variables: list[VariableDef] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
```

**2. `src/xianyu/html_scene/interpolation.py`（新建）**

```python
"""变量插值引擎 — schema-aware Jinja2 渲染封装。

核心功能：
  1. extract_variable_refs() — 从模板 AST 提取变量引用
  2. InterpolationEngine — 校验变量 schema 后渲染

数据流：
  TemplateRegistry 在 discover() 时调用 extract_variable_refs()
  获取模板实际使用的变量，自动生成 VariableDef。
  InterpolationEngine.render() 在渲染前校验变量完整性和类型。
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from jinja2 import Environment, BaseLoader, TemplateNotFound, meta
from jinja2.exceptions import UndefinedError
from loguru import logger

from xianyu.html_scene.schema import TemplateMeta, VariableDef, VariableType

# ── 全局 Jinja2 环境（无 loader，模板作为字符串传入） ──
_JINJA = Environment(autoescape=False)


def extract_variable_refs(template_content: str) -> set[str]:
    """从 Jinja2 模板 AST 中提取所有引用的变量名。

    通过 jinja2.meta.find_undeclared_variables() 覆盖 {{ var }} 表达式。
    额外扫描 {% if var %} 等块中的变量（jinja2.meta 默认覆盖）。

    Args:
        template_content: Jinja2 模板原始内容。

    Returns:
        模板中引用的变量名称集合。
    """
    ast = _JINJA.parse(template_content)
    return meta.find_undeclared_variables(ast)


def _coerce_value(value: Any, var_type: VariableType) -> Any:
    """将值按 VariableType 做类型转换。

    转换规则：
      - STR: str(value)
      - INT: int(value)（None → 0）
      - FLOAT: float(value)（None → 0.0）
      - BOOL: bool(value)

    Raises:
        TypeError: 类型转换失败（int/float 传无法解析的字符串）。
    """
    if value is None:
        return None
    try:
        if var_type == VariableType.STR:
            return str(value)
        if var_type == VariableType.INT:
            return int(value)
        if var_type == VariableType.FLOAT:
            return float(value)
        if var_type == VariableType.BOOL:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
    except (ValueError, TypeError) as exc:
        raise TypeError(f"变量类型转换失败: {value!r} → {var_type.value}: {exc}") from exc
    return value


class InterpolationEngine:
    """变量插值引擎 — schema-aware Jinja2 渲染。

    用法:
        engine = InterpolationEngine()
        html = engine.render(template_str, {"scene_title": "你好", ...}, schema=meta.variables)
    """

    def __init__(self, strict_unknown: bool = False) -> None:
        self._jinja = Environment(autoescape=False)
        self.strict_unknown = strict_unknown

    def render(
        self,
        template_content: str,
        variables: Mapping[str, Any],
        schema: list[VariableDef] | None = None,
    ) -> str:
        """渲染模板，含 schema 校验。

        Args:
            template_content: Jinja2 模板原始内容。
            variables: 要注入的变量值。
            schema: 变量 schema 定义列表。None = 跳过校验，直接渲染。

        Returns:
            渲染后的 HTML 字符串。

        Raises:
            ValueError: required 变量缺失。
            TypeError: 变量类型转换失败。
            jinja2.TemplateError: 模板语法错误。
        """
        if schema is not None:
            variables = self._validate_and_prepare(variables, schema)

        template = self._jinja.from_string(template_content)
        try:
            return template.render(**variables)
        except UndefinedError as exc:
            logger.warning("[interpolation] 模板渲染引用未定义变量: {}", exc)
            raise

    def render_safe(
        self,
        template_content: str,
        variables: Mapping[str, Any],
        schema: list[VariableDef] | None = None,
    ) -> str:
        """安全渲染：校验异常返回空字符串 + log error。"""
        try:
            return self.render(template_content, variables, schema)
        except (ValueError, TypeError, Exception) as exc:
            logger.error("[interpolation] 渲染失败: {}", exc)
            return ""

    def _validate_and_prepare(
        self,
        variables: Mapping[str, Any],
        schema: list[VariableDef],
    ) -> dict[str, Any]:
        """校验 + 准备变量。

        步骤：
          1. 检查 required 变量是否全部提供
          2. 为缺失的 optional 变量填充默认值
          3. 类型转换已提供的变量
          4. 过滤未在 schema 中声明的变量（仅 strict_unknown=True 时警告）

        Returns:
            处理后的变量字典（仅包含 schema 中声明的变量）。
        """
        schema_map: dict[str, VariableDef] = {v.name: v for v in schema}
        result: dict[str, Any] = {}

        # ── 检查 required ──
        missing = [v.name for v in schema if v.required and v.name not in variables]
        if missing:
            raise ValueError(f"缺少 required 变量: {', '.join(missing)}")

        # ── 填充 optional 默认值 + 类型转换 ──
        for vdef in schema:
            if vdef.name in variables:
                result[vdef.name] = _coerce_value(variables[vdef.name], vdef.type)
            elif vdef.default is not None:
                result[vdef.name] = vdef.default
            # 如果既没提供又无默认值，跳过（Jinja2 的 {{ }} 会变成 ''）

        # ── 未知变量警告 ──
        unknown = set(variables.keys()) - set(schema_map.keys())
        if unknown and self.strict_unknown:
            logger.warning(
                "[interpolation] 变量不在 schema 中，已忽略: {}",
                ", ".join(sorted(unknown)),
            )

        return result

    def validate_render(
        self,
        template_content: str,
        sample_variables: Mapping[str, Any],
        schema: list[VariableDef] | None = None,
    ) -> list[str]:
        """用样本变量试渲染，返回错误列表。"""
        errors: list[str] = []
        try:
            # 先单变量验证
            meta_ast = _JINJA.parse(template_content)
            refs = meta.find_undeclared_variables(meta_ast)
            if schema:
                declared = {v.name for v in schema}
                unrefed = declared - refs
                undeclared = refs - declared
                if unrefed:
                    errors.append(f"声明但未使用的变量: {', '.join(sorted(unrefed))}")
                if undeclared:
                    errors.append(f"模板引用未声明的变量: {', '.join(sorted(undeclared))}")

            # 实际渲染
            self.render(template_content, sample_variables, schema)
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"渲染异常: {exc}")

        return errors


__all__ = [
    "InterpolationEngine",
    "extract_variable_refs",
    "_coerce_value",
]
```

**3. `src/xianyu/html_scene/registry.py`（新建）**

```python
"""TemplateRegistry — HTML 场景模板注册表。

模板发现 + 元数据管理 + 缓存。

层次：
  - TemplateInfo: 运行时模板对象（元数据 + 原始内容 + 来源标记）
  - TemplateRegistry: 注册表（discover / register / get / list）

设计原则：
  - 内置目录自动发现，不依赖任何配置文件
  - 无元数据的模板自动通过 extract_variable_refs 推断变量
  - 外部路径注册后自动增量扫描，不重复加载已有模板
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment
from loguru import logger

from xianyu.html_scene.schema import SceneStyle, TemplateMeta, VariableDef, VariableType

from .interpolation import extract_variable_refs

# 内置模板目录（相对于本文件）
_BUILTIN_DIR = Path(__file__).resolve().parent / "templates"

# Jinja2 用于变量提取的环境实例（无 autoescape）
_EXTRACT_ENV = Environment(autoescape=False)


class TemplateInfo:
    """运行时模板对象。

    Attributes:
        metadata: 模板元数据（内置模板自动生成，外部模板由 register() 提供）。
        source: 来源类型（"builtin" / "external" / "registered"）。
        source_path: 模板文件路径（builtin/external）或 None（registered from string）。
        content: 模板原始 HTML 内容。
    """

    def __init__(
        self,
        metadata: TemplateMeta,
        source: str,
        source_path: str | Path | None = None,
        content: str = "",
    ) -> None:
        self.metadata = metadata
        self.source = source
        self.source_path = str(source_path) if source_path else ""
        self._content = content

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value

    def __repr__(self) -> str:
        return f"TemplateInfo(name={self.metadata.name!r}, source={self.source})"


def _build_auto_meta(
    name: str,
    content: str,
    style: SceneStyle | None = None,
) -> TemplateMeta:
    """为无元数据的模板自动生成 TemplateMeta。

    通过 extract_variable_refs() 解析变量引用，全部标记为 type=str, required=False。
    style 从文件名推断：与 SceneStyle 枚举值匹配则关联，否则 SceneStyle.MINIMAL。
    """
    refs = extract_variable_refs(content)
    variables = [
        VariableDef(
            name=v,
            type=VariableType.STR,
            description=f"模板变量: {v}",
            required=False,
        )
        for v in sorted(refs)
    ]

    if style is None:
        try:
            style = SceneStyle(name)
        except ValueError:
            style = SceneStyle.MINIMAL

    return TemplateMeta(
        name=name,
        description=f"Auto-detected template: {name}",
        style=style,
        variables=variables,
        tags=["auto-detected"],
    )


class TemplateRegistry:
    """HTML 场景模板注册表。

    用法:
        registry = TemplateRegistry()
        count = registry.discover()       # 扫描内置目录
        registry.add_path("/my/templates")  # 添加外部路径
        tpl = registry.get_template("minimal")  # 按名获取
        lst = registry.list_templates(style=SceneStyle.TECH)  # 按风格筛选

        # 动态注册字符串模板
        registry.register("dynamic", "<html>{{ var }}</html>", meta=TemplateMeta(...))
    """

    def __init__(self, builtin_dir: str | Path | None = None) -> None:
        self._builtin_dir = Path(builtin_dir) if builtin_dir else _BUILTIN_DIR
        self._templates: dict[str, TemplateInfo] = {}
        self._extra_paths: list[Path] = []
        self._discovered = False

    # ── 发现 ──

    def discover(self) -> int:
        """扫描内置模板目录，加载所有 .html 模板。

        跳过 __init__.py / __pycache__ 等非模板文件。
        已有同名的模板不会覆盖（优先保留已注册的）。

        Returns:
            新发现的模板数量。
        """
        count = 0
        if not self._builtin_dir.is_dir():
            logger.warning("[registry] 内置模板目录不存在: {}", self._builtin_dir)
            return 0

        for html_path in sorted(self._builtin_dir.glob("*.html")):
            name = html_path.stem
            if name == "__init__":
                continue

            if name in self._templates:
                continue  # 已有注册，避免覆盖

            content = html_path.read_text(encoding="utf-8")
            meta = _build_auto_meta(name, content)
            self._templates[name] = TemplateInfo(
                metadata=meta,
                source="builtin",
                source_path=html_path,
                content=content,
            )
            count += 1

        self._discovered = True
        logger.info("[registry] 发现 {} 个内置模板", count)
        return count

    def add_path(self, path: str | Path) -> int:
        """添加外部模板搜索路径，增量扫描。

        返回新发现的模板数。已存在的模板名不会被覆盖。

        Args:
            path: 外部模板目录路径。

        Returns:
            新发现的模板数量。
        """
        p = Path(path)
        if not p.is_dir():
            logger.warning("[registry] 外部目录不存在: {}", p)
            return 0

        self._extra_paths.append(p)
        count = 0
        for html_path in sorted(p.glob("*.html")):
            name = html_path.stem
            if name in self._templates:
                continue
            content = html_path.read_text(encoding="utf-8")
            meta = _build_auto_meta(name, content)
            self._templates[name] = TemplateInfo(
                metadata=meta,
                source="external",
                source_path=html_path,
                content=content,
            )
            count += 1

        if count:
            logger.info("[registry] 从 {} 发现 {} 个模板", p, count)
        return count

    # ── 注册 ──

    def register(
        self,
        name: str,
        content: str,
        meta: TemplateMeta | None = None,
        style: SceneStyle | None = None,
    ) -> TemplateInfo:
        """动态注册一个模板（内存中，不写文件）。

        Args:
            name: 模板名（必须匹配 TemplateMeta.name pattern）。
            content: 模板 HTML 内容。
            meta: 可选的 TemplateMeta。None 时自动生成。
            style: 当 meta 为 None 时的风格提示。

        Returns:
            创建的 TemplateInfo 实例。

        Raises:
            ValueError: name 已存在。
        """
        if name in self._templates:
            raise ValueError(f"模板已存在: {name}")

        if meta is not None:
            meta.name = name  # 强制覆盖 name 以匹配注册名
        else:
            meta = _build_auto_meta(name, content, style=style)

        info = TemplateInfo(
            metadata=meta,
            source="registered",
            content=content,
        )
        self._templates[name] = info
        logger.info("[registry] 注册模板: {} ({} vars)", name, len(meta.variables))
        return info

    # ── 查询 ──

    def get_template(self, name: str) -> TemplateInfo:
        """按名称查询模板。

        Raises:
            KeyError: 模板不存在。
        """
        if name not in self._templates:
            raise KeyError(f"模板不存在: {name}")
        return self._templates[name]

    def list_templates(
        self,
        style: SceneStyle | None = None,
        tag: str | None = None,
    ) -> list[TemplateInfo]:
        """列出注册的模板，按名称排序。

        Args:
            style: 按风格筛选（None = 不过滤）。
            tag: 按标签筛选（None = 不过滤）。

        Returns:
            匹配的模板列表。
        """
        result = list(self._templates.values())
        if style is not None:
            result = [t for t in result if t.metadata.style == style]
        if tag is not None:
            result = [t for t in result if tag in t.metadata.tags]
        result.sort(key=lambda t: t.metadata.name)
        return result

    @property
    def count(self) -> int:
        return len(self._templates)

    def reload(self) -> int:
        """重新发现内置 + 外部路径的模板，更新缓存。

        已通过 register() 注册的（source="registered"）模板不受影响。
        覆盖已有同名内置/外部模板的内容。

        Returns:
            更新的模板数量。
        """
        # 清除非 registered 的模板
        to_keep = {
            name: info
            for name, info in self._templates.items()
            if info.source == "registered"
        }
        self._templates = to_keep

        count = 0
        # 重扫内置
        if self._builtin_dir.is_dir():
            for html_path in sorted(self._builtin_dir.glob("*.html")):
                name = html_path.stem
                if name == "__init__" or name in self._templates:
                    continue
                content = html_path.read_text(encoding="utf-8")
                self._templates[name] = TemplateInfo(
                    metadata=_build_auto_meta(name, content),
                    source="builtin",
                    source_path=html_path,
                    content=content,
                )
                count += 1

        # 重扫外部
        for p in self._extra_paths:
            for html_path in sorted(p.glob("*.html")):
                name = html_path.stem
                if name in self._templates:
                    continue
                self._templates[name] = TemplateInfo(
                    metadata=_build_auto_meta(name, html_path.read_text(encoding="utf-8")),
                    source="external",
                    source_path=html_path,
                    content=html_path.read_text(encoding="utf-8"),
                )
                count += 1

        logger.info("[registry] reload 完成: {} 个模板", self.count)
        return count


__all__ = [
    "TemplateInfo",
    "TemplateRegistry",
    "_build_auto_meta",
]
```

**4. `src/xianyu/html_scene/validation.py`（新建）**

```python
"""模板校验系统 — 三层校验。

1. HTML 结构校验：检查 DOCTYPE、标签闭合、<html>/<head>/<body>
2. 变量校验：模板实际引用 vs 声明变量的对比
3. 渲染校验：试渲染验证

ValidationResult 带 errors / warnings / info 三列表，不抛异常。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from xianyu.html_scene.interpolation import InterpolationEngine, extract_variable_refs
from xianyu.html_scene.schema import TemplateMeta, VariableDef


@dataclass
class ValidationIssue:
    """校验发现的一个问题。"""
    message: str
    severity: str = "error"  # "error" | "warning" | "info"
    line: int = 0
    column: int = 0

    def __repr__(self) -> str:
        loc = f" (L{self.line}" + (f":{self.column})" if self.column else ")") if self.line else ""
        return f"[{self.severity.upper()}] {self.message}{loc}"


@dataclass
class ValidationResult:
    """模板校验结果。"""
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """无 error 即视为 valid。"""
        return len(self.errors) == 0

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)


# ── XML/HTML 标签正则（用于基础结构检测，不依赖外部解析器） ──
_RE_DOCTYPE = re.compile(r"<!DOCTYPE\s+html", re.IGNORECASE)
_RE_HTML_OPEN = re.compile(r"<html[\s>]", re.IGNORECASE)
_RE_HTML_CLOSE = re.compile(r"</html>", re.IGNORECASE)
_RE_HEAD_OPEN = re.compile(r"<head[\s>]", re.IGNORECASE)
_RE_HEAD_CLOSE = re.compile(r"</head>", re.IGNORECASE)
_RE_BODY_OPEN = re.compile(r"<body[\s>]", re.IGNORECASE)
_RE_BODY_CLOSE = re.compile(r"</body>", re.IGNORECASE)
_RE_TITLE_OPEN = re.compile(r"<title[\s>]", re.IGNORECASE)
_RE_TITLE_CLOSE = re.compile(r"</title>", re.IGNORECASE)
_RE_STYLE_OPEN = re.compile(r"<style[\s>]", re.IGNORECASE)
_RE_STYLE_CLOSE = re.compile(r"</style>", re.IGNORECASE)
_RE_META_CHARSET = re.compile(r'<meta\s+[^>]*charset\s*=', re.IGNORECASE)
_RE_VIEWPORT = re.compile(r'<meta\s+[^>]*name\s*=\s*["\']viewport["\']', re.IGNORECASE)

# 标签匹配（用于检测未闭合标签，简化版）
_RE_OPEN_TAG = re.compile(r"<(?!/)([a-zA-Z0-9]+)[^>]*>")


def _line_no(content: str, offset: int) -> int:
    """计算字符串中偏移量对应的行号。"""
    return content[:offset].count("\n") + 1


def validate_html_structure(template_content: str) -> ValidationResult:
    """HTML 结构基础校验。

    检查：
      - DOCTYPE 声明
      - <html> / <head> / <body> 标签对
      - <title> 和 <style> 标签基础结构
      - <meta charset> 声明
      - viewport meta
    """
    result = ValidationResult()

    if not template_content or not template_content.strip():
        result.errors.append(ValidationIssue("模板内容为空"))
        return result

    checks: list[tuple[str, re.Pattern, bool, str]] = [
        ("DOCTYPE 声明", _RE_DOCTYPE, True, "缺少 DOCTYPE 声明：<!DOCTYPE html>"),
        ("<html>", _RE_HTML_OPEN, True, "缺少 <html> 开始标签"),
        ("</html>", _RE_HTML_CLOSE, True, "缺少 </html> 结束标签"),
        ("<head>", _RE_HEAD_OPEN, True, "缺少 <head>"),
        ("</head>", _RE_HEAD_CLOSE, True, "缺少 </head>"),
        ("<body>", _RE_BODY_OPEN, True, "缺少 <body>"),
        ("</body>", _RE_BODY_CLOSE, True, "缺少 </body>"),
        ("<title>", _RE_TITLE_OPEN, True, "缺少 <title>"),
        ("</title>", _RE_TITLE_CLOSE, True, "缺少 </title>"),
        ("<style>", _RE_STYLE_OPEN, True, "缺少 <style> 块"),
        ("</style>", _RE_STYLE_CLOSE, True, "缺少 </style> 结束"),
        ("<meta charset>", _RE_META_CHARSET, False, "建议添加 <meta charset=\"utf-8\">"),
        ("viewport meta", _RE_VIEWPORT, False, "建议添加 viewport <meta>"),
    ]

    for name, pattern, is_required, msg in checks:
        match = pattern.search(template_content)
        if match:
            result.info.append(ValidationIssue(
                message=f"{name} ✓",
                severity="info",
                line=_line_no(template_content, match.start()),
            ))
        elif is_required:
            result.errors.append(ValidationIssue(message=msg))
        else:
            result.warnings.append(ValidationIssue(message=msg))

    # ── 简单的标签计数闭合检查（不完美但覆盖常见问题） ──
    open_tags: dict[str, int] = {}
    close_tags: dict[str, int] = {}
    for m in _RE_OPEN_TAG.finditer(template_content):
        tag = m.group(1).lower()
        if tag in ("br", "hr", "img", "input", "meta", "link", "source"):
            continue  # 自闭合 / void 元素
        open_tags[tag] = open_tags.get(tag, 0) + 1

    for m in re.finditer(r"</([a-zA-Z0-9]+)>", template_content):
        tag = m.group(1).lower()
        close_tags[tag] = close_tags.get(tag, 0) + 1

    for tag, ocount in open_tags.items():
        ccount = close_tags.get(tag, 0)
        if ocount > ccount:
            result.warnings.append(ValidationIssue(
                message=f"标签 <{tag}> 可能未闭合（{ocount} 开 {ccount} 闭）",
                severity="warning",
            ))

    return result


def validate_variable_consistency(
    template_content: str,
    declared_vars: list[VariableDef],
) -> ValidationResult:
    """校验模板变量一致性。

    对比：
      - 模板实际引用的变量 vs 声明的变量列表
      - 声明未使用的变量（warning）
      - 使用未声明的变量（warning）
    """
    result = ValidationResult()
    refs = extract_variable_refs(template_content)
    declared_names = {v.name for v in declared_vars}

    undeclared = refs - declared_names
    if undeclared:
        result.warnings.append(ValidationIssue(
            message=f"模板引用了未声明的变量: {', '.join(sorted(undeclared))}",
            severity="warning",
        ))

    unused = declared_names - refs
    if unused:
        result.warnings.append(ValidationIssue(
            message=f"声明了但模板未使用的变量: {', '.join(sorted(unused))}",
            severity="warning",
        ))

    if not undeclared and not unused:
        result.info.append(ValidationIssue(
            message="变量一致性检查通过",
            severity="info",
        ))

    return result


def validate_template(
    template_content: str,
    meta: TemplateMeta | None = None,
    sample_variables: dict[str, Any] | None = None,
) -> ValidationResult:
    """综合校验：结构 + 变量 + 渲染。

    这是最常用的校验入口。

    Args:
        template_content: 模板原始 HTML 内容。
        meta: 可选的 TemplateMeta（提供变量声明等）。
        sample_variables: 用于试渲染的样本变量值。

    Returns:
        综合校验结果。
    """
    result = ValidationResult()

    # 1. HTML 结构
    result.merge(validate_html_structure(template_content))

    # 2. 变量一致性
    if meta is not None and meta.variables:
        result.merge(validate_variable_consistency(template_content, meta.variables))

    # 3. 渲染校验
    if sample_variables is not None:
        engine = InterpolationEngine()
        render_errors = engine.validate_render(
            template_content,
            sample_variables,
            meta.variables if meta else None,
        )
        for err in render_errors:
            result.errors.append(ValidationIssue(message=err))

    return result


__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "validate_html_structure",
    "validate_variable_consistency",
    "validate_template",
]
```

**5. `src/xianyu/html_scene/schema.py` — 导入变更**

在文件顶部追加导入（在现有 `from __future__ import annotations` 等之后，`SceneStyle` 定义之前）：

```python
from typing import Any
```

在 `SceneScript` 模型之后追加模型导入（保持向后兼容）：

（上面第 1 步的 `VariableType` / `VariableDef` / `TemplateMeta` 定义直接追加在 `SceneScript` 之后，不修改现有类。）

**6. `src/xianyu/html_scene/agent.py` — 选择性集成**

(a) 新增 import：

```python
from xianyu.html_scene.registry import TemplateRegistry
from xianyu.html_scene.interpolation import InterpolationEngine
```

(b) 在 `render_scene_html()` 中新增可选 `registry` 参数：

```python
def render_scene_html(
    scene: SceneDescription,
    index: int,
    total: int,
    *,
    registry: TemplateRegistry | None = None,
) -> str:
    """Render a single SceneDescription into an HTML string.

    当传入了 registry 参数时，走 schema-aware 渲染路径（通过 InterpolationEngine）：
      - 从 registry 获取模板元数据（变量 schema）
      - 校验变量完整性与类型
      - 渲染
    不传 registry 时保持原有硬编码 Jinja2 渲染，零回归。
    """
    template_name = f"{scene.style.value}.html"
    variables = {
        "scene_title": scene.title,
        "scene_subtitle": scene.subtitle,
        "scene_content": scene.content,
        "scene_index": index,
        "total_scenes": total,
        "duration": scene.duration,
    }

    if registry is not None:
        try:
            tpl_info = registry.get_template(scene.style.value)
            engine = InterpolationEngine()
            return engine.render(tpl_info.content, variables, tpl_info.metadata.variables)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(
                "[agent] schema-aware 渲染失败 (template={}), 回退硬编码: {}",
                scene.style.value, exc,
            )
            # 回退到原有渲染

    template = _JINJA_ENV.get_template(template_name)
    return template.render(**variables)
```

注意：`_JINJA_ENV` 在 `agent.py` 第 22-25 行定义，保持不变。

(c) 修改 `generate_all_html()` 新增 `registry` 参数透传：

```python
def generate_all_html(
    script: SceneScript,
    output_dir: str | Path,
    *,
    registry: TemplateRegistry | None = None,
) -> list[Path]:
    """Generate HTML files for all scenes in a SceneScript."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i, scene in enumerate(script.scenes, start=1):
        html = render_scene_html(scene, i, len(script.scenes), registry=registry)
        file_path = out / f"scene_{i:03d}.html"
        file_path.write_text(html, encoding="utf-8")
        paths.append(file_path)
        logger.debug("Wrote scene HTML: {}", file_path)

    return paths
```

(d) 修改 `ab_compare_templates()` 新增 `registry` 参数透传：

```python
def ab_compare_templates(
    scene: SceneDescription,
    index: int,
    total: int,
    styles: list[SceneStyle] | None = None,
    *,
    registry: TemplateRegistry | None = None,
) -> dict[str, str]:
    # ... 保持不变，但内部调用 render_scene_html 时传 registry
```

调用处 `render_scene_html(scene, index, total, registry=registry)`。

实际改动较小：只在两个调用 `render_scene_html()` 的地方加上 `registry=registry` 参数透传。

**7. `src/xianyu/html_scene/__init__.py` — 更新导出**

```python
"""HTML scene generation module for xianyu v2 video pipeline.

Provides schema definitions, LLM agent for scene generation, Jinja2
templates, and Playwright-based rendering for the HTML→Video pipeline.

Added in tmpl-html-scene: TemplateRegistry, InterpolationEngine, Validation.
"""

from xianyu.html_scene.agent import (
    ab_compare_templates,
    generate_all_html,
    generate_scene_script,
    render_scene_html,
)
from xianyu.html_scene.interpolation import InterpolationEngine, extract_variable_refs
from xianyu.html_scene.registry import TemplateInfo, TemplateRegistry
from xianyu.html_scene.renderer import render_scene_frames
from xianyu.html_scene.schema import (
    SceneDescription,
    SceneScript,
    SceneStyle,
    TemplateMeta,
    VariableDef,
    VariableType,
)
from xianyu.html_scene.validation import (
    ValidationIssue,
    ValidationResult,
    validate_html_structure,
    validate_template,
    validate_variable_consistency,
)

__all__ = [
    "SceneDescription",
    "SceneScript",
    "SceneStyle",
    "TemplateMeta",
    "TemplateRegistry",
    "TemplateInfo",
    "VariableDef",
    "VariableType",
    "InterpolationEngine",
    "extract_variable_refs",
    "ValidationIssue",
    "ValidationResult",
    "validate_html_structure",
    "validate_template",
    "validate_variable_consistency",
    "ab_compare_templates",
    "generate_scene_script",
    "generate_all_html",
    "render_scene_html",
    "render_scene_frames",
]
```

**8. `tests/html_scene/test_registry.py`（新建）**

```python
"""TemplateRegistry — 模板注册表单元测试。"""
from __future__ import annotations

import pytest

from xianyu.html_scene.registry import TemplateInfo, TemplateRegistry, _build_auto_meta
from xianyu.html_scene.schema import TemplateMeta, VariableDef, VariableType, SceneStyle


class TestBuildAutoMeta:
    def test_extracts_variables(self) -> None:
        content = "<html><body>{{ scene_title }} - {{ scene_content }}</body></html>"
        meta = _build_auto_meta("test", content)
        var_names = {v.name for v in meta.variables}
        assert var_names == {"scene_title", "scene_content"}
        assert all(v.type == VariableType.STR for v in meta.variables)
        assert all(not v.required for v in meta.variables)

    def test_extracts_if_variable(self) -> None:
        content = "{% if scene_subtitle %}{{ scene_subtitle }}{% endif %}"
        meta = _build_auto_meta("test2", content)
        var_names = {v.name for v in meta.variables}
        assert "scene_subtitle" in var_names

    def test_empty_template_no_vars(self) -> None:
        meta = _build_auto_meta("empty", "")
        assert meta.variables == []

    def infers_style_from_name(self) -> None:
        meta = _build_auto_meta("tech", "{{ x }}")
        assert meta.style == SceneStyle.TECH

    def test_unknown_style_defaults_to_minimal(self) -> None:
        meta = _build_auto_meta("unknown_style", "{{ x }}")
        assert meta.style == SceneStyle.MINIMAL

    def test_auto_meta_tags(self) -> None:
        meta = _build_auto_meta("test", "{{ a }}")
        assert "auto-detected" in meta.tags


class TestTemplateRegistry:
    def test_discover_finds_builtins(self) -> None:
        """内置目录的 discover() 应找到 7 个标准模板。"""
        registry = TemplateRegistry()
        count = registry.discover()
        assert count >= 7
        assert registry.count >= 7

    def test_get_template_by_name(self) -> None:
        registry = TemplateRegistry()
        registry.discover()
        tpl = registry.get_template("minimal")
        assert isinstance(tpl, TemplateInfo)
        assert tpl.metadata.name == "minimal"
        assert "<!DOCTYPE html>" in tpl.content

    def test_get_template_raises_on_missing(self) -> None:
        registry = TemplateRegistry()
        with pytest.raises(KeyError, match="不存在"):
            registry.get_template("nonexistent")

    def test_list_templates_all(self) -> None:
        registry = TemplateRegistry()
        registry.discover()
        all_tpl = registry.list_templates()
        assert len(all_tpl) >= 7

    def test_list_templates_by_style(self) -> None:
        registry = TemplateRegistry()
        registry.discover()
        tech_tpl = registry.list_templates(style=SceneStyle.TECH)
        assert len(tech_tpl) >= 1
        assert all(t.metadata.style == SceneStyle.TECH for t in tech_tpl)

    def test_register_new_template(self) -> None:
        registry = TemplateRegistry()
        content = "<html><body>{{ my_var }}</body></html>"
        meta = TemplateMeta(
            name="custom",
            description="Custom template",
            variables=[VariableDef(name="my_var", type=VariableType.STR, required=True)],
        )
        info = registry.register("custom", content, meta=meta)
        assert info.source == "registered"
        assert info.content == content
        assert registry.count == 1

    def test_register_duplicate_raises(self) -> None:
        registry = TemplateRegistry()
        registry.register("dup", "content")
        with pytest.raises(ValueError, match="已存在"):
            registry.register("dup", "other")

    def test_reload_preserves_registered(self) -> None:
        """reload() 不覆盖通过 register() 注册的模板。"""
        registry = TemplateRegistry()
        registry.register("my_custom", "content")
        registry.reload()
        assert registry.count >= 1  # 保留 registered

    def test_add_path_nonexistent(self) -> None:
        registry = TemplateRegistry()
        count = registry.add_path("/tmp/nonexistent_dir_12345")
        assert count == 0
```

**9. `tests/html_scene/test_interpolation.py`（新建）**

```python
"""InterpolationEngine — 变量插值引擎单元测试。"""
from __future__ import annotations

import pytest

from xianyu.html_scene.interpolation import (
    InterpolationEngine,
    _coerce_value,
    extract_variable_refs,
)
from xianyu.html_scene.schema import VariableDef, VariableType


class TestExtractVariableRefs:
    def test_simple_refs(self) -> None:
        refs = extract_variable_refs("{{ a }} and {{ b }}")
        assert refs == {"a", "b"}

    def test_if_block(self) -> None:
        refs = extract_variable_refs("{% if x %}{{ x }}{% endif %}")
        assert "x" in refs

    def test_filter_chain(self) -> None:
        refs = extract_variable_refs("{{ name|default('x')|upper }}")
        assert "name" in refs

    def test_no_vars(self) -> None:
        refs = extract_variable_refs("<html><body>static</body></html>")
        assert refs == set()

    def test_multiple_occurrences(self) -> None:
        refs = extract_variable_refs("{{ x }} - {{ x }} - {{ y }}")
        assert refs == {"x", "y"}


class TestCoerceValue:
    def test_str(self) -> None:
        assert _coerce_value("hello", VariableType.STR) == "hello"
        assert _coerce_value(42, VariableType.STR) == "42"

    def test_int(self) -> None:
        assert _coerce_value("42", VariableType.INT) == 42
        assert _coerce_value(3.14, VariableType.INT) == 3

    def test_float(self) -> None:
        assert _coerce_value("3.14", VariableType.FLOAT) == 3.14
        assert _coerce_value(42, VariableType.FLOAT) == 42.0

    def test_bool(self) -> None:
        assert _coerce_value("true", VariableType.BOOL) is True
        assert _coerce_value("false", VariableType.BOOL) is False
        assert _coerce_value(1, VariableType.BOOL) is True
        assert _coerce_value(0, VariableType.BOOL) is False

    def test_none_returns_none(self) -> None:
        assert _coerce_value(None, VariableType.STR) is None

    def test_invalid_int_raises(self) -> None:
        with pytest.raises(TypeError):
            _coerce_value("not_a_number", VariableType.INT)


class TestInterpolationEngine:
    def test_render_simple(self) -> None:
        engine = InterpolationEngine()
        html = engine.render("Hello {{ name }}!", {"name": "World"})
        assert html == "Hello World!"

    def test_render_with_schema(self) -> None:
        engine = InterpolationEngine()
        schema = [VariableDef(name="name", type=VariableType.STR, required=True)]
        html = engine.render("Hello {{ name }}!", {"name": "World"}, schema)
        assert html == "Hello World!"

    def test_missing_required_raises(self) -> None:
        engine = InterpolationEngine()
        schema = [VariableDef(name="required_var", type=VariableType.STR, required=True)]
        with pytest.raises(ValueError, match="required"):
            engine.render("{{ required_var }}", {}, schema)

    def test_default_value_filled(self) -> None:
        engine = InterpolationEngine()
        schema = [
            VariableDef(
                name="opt", type=VariableType.STR, required=False, default="default_val"
            ),
        ]
        html = engine.render("{{ opt }}", {}, schema)
        assert "default_val" in html

    def test_type_coercion(self) -> None:
        engine = InterpolationEngine()
        schema = [VariableDef(name="num", type=VariableType.INT, required=True)]
        html = engine.render("Number: {{ num }}", {"num": "42"}, schema)
        assert "42" in html

    def test_render_safe_fallback(self) -> None:
        engine = InterpolationEngine()
        result = engine.render_safe("{{ missing }}", {}, [])
        assert result == ""

    def test_unknown_var_no_warning_by_default(self) -> None:
        """strict_unknown=False 时不发出警告。"""
        engine = InterpolationEngine(strict_unknown=False)
        schema = [VariableDef(name="known", type=VariableType.STR)]
        html = engine.render("{{ known }}", {"known": "ok", "extra": "ignored"}, schema)
        assert html == "ok"  # extra 被忽略

    def test_validate_render_passes(self) -> None:
        engine = InterpolationEngine()
        schema = [VariableDef(name="x", type=VariableType.STR, required=True)]
        errors = engine.validate_render("{{ x }}", {"x": "ok"}, schema)
        assert errors == []

    def test_validate_render_detects_unused_var(self) -> None:
        engine = InterpolationEngine()
        schema = [
            VariableDef(name="used", type=VariableType.STR),
            VariableDef(name="unused", type=VariableType.STR),
        ]
        errors = engine.validate_render("{{ used }}", {"used": "x"}, schema)
        assert any("未使用" in e for e in errors)
```

**10. `tests/html_scene/test_validation.py`（新建）**

```python
"""Validation — 模板校验单元测试。"""
from __future__ import annotations

import pytest

from xianyu.html_scene.schema import TemplateMeta, VariableDef, VariableType
from xianyu.html_scene.validation import (
    ValidationResult,
    validate_html_structure,
    validate_template,
    validate_variable_consistency,
)


_VALID_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920,height=1080">
<title>{{ scene_title }}</title>
<style>
body { background: #fff; }
</style>
</head>
<body>
<div>{{ scene_content }}</div>
</body>
</html>"""


class TestValidateHtmlStructure:
    def test_valid_html_passes(self) -> None:
        result = validate_html_structure(_VALID_HTML)
        assert result.is_valid

    def test_empty_content_errors(self) -> None:
        result = validate_html_structure("")
        assert not result.is_valid

    def test_missing_doctype(self) -> None:
        content = "<html><body></body></html>"
        result = validate_html_structure(content)
        assert len(result.errors) > 0

    def test_missing_html_tag(self) -> None:
        content = "<body></body>"
        result = validate_html_structure(content)
        assert not result.is_valid

    def test_missing_head(self) -> None:
        content = "<!DOCTYPE html><html><body></body></html>"
        result = validate_html_structure(content)
        assert not result.is_valid

    def test_missing_title(self) -> None:
        content = "<!DOCTYPE html><html><head></head><body></body></html>"
        result = validate_html_structure(content)
        assert not result.is_valid

    def test_missing_style(self) -> None:
        content = "<!DOCTYPE html><html><head><title>T</title></head><body></body></html>"
        result = validate_html_structure(content)
        assert not result.is_valid

    def test_unclosed_tag_detected(self) -> None:
        content = "<!DOCTYPE html><html><body><div><span>text</div></body></html>"
        # <span> 没有 </span>
        result = validate_html_structure(content)
        unclosed = [w for w in result.warnings if "未闭合" in w.message]
        assert len(unclosed) >= 1


class TestValidateVariableConsistency:
    def test_all_consistent(self) -> None:
        content = "{{ used_var }}"
        declared = [VariableDef(name="used_var", type=VariableType.STR)]
        result = validate_variable_consistency(content, declared)
        assert result.is_valid

    def test_undeclared_var_warning(self) -> None:
        content = "{{ undeclared_var }}"
        result = validate_variable_consistency(content, [])
        assert len(result.warnings) >= 1
        assert "未声明" in result.warnings[0].message

    def test_unused_var_warning(self) -> None:
        content = "static"
        declared = [VariableDef(name="unused_var", type=VariableType.STR)]
        result = validate_variable_consistency(content, declared)
        assert len(result.warnings) >= 1
        assert "未使用" in result.warnings[0].message


class TestValidateTemplate:
    def test_valid_template(self) -> None:
        meta = TemplateMeta(
            name="test",
            variables=[
                VariableDef(name="scene_title", type=VariableType.STR),
                VariableDef(name="scene_content", type=VariableType.STR),
            ],
        )
        result = validate_template(
            _VALID_HTML,
            meta=meta,
            sample_variables={"scene_title": "T", "scene_content": "C"},
        )
        assert result.is_valid

    def test_missing_required_raises_render_error(self) -> None:
        meta = TemplateMeta(
            name="test",
            variables=[VariableDef(name="required_var", type=VariableType.STR, required=True)],
        )
        # 模板中引用 required_var，但 sample_variables 中不提供
        content = "{{ required_var }}"
        result = validate_template(
            content,
            meta=meta,
            sample_variables={},
        )
        assert not result.is_valid

    def test_info_messages_exist(self) -> None:
        result = validate_template(_VALID_HTML)
        assert len(result.info) > 0

    def test_merge(self) -> None:
        r1 = ValidationResult()
        r1.errors.append(ValidationIssue(message="e1"))
        r2 = ValidationResult()
        r2.warnings.append(ValidationIssue(message="w1"))
        r1.merge(r2)
        assert len(r1.errors) == 1
        assert len(r1.warnings) == 1
```

### 验收清单

- [ ] `TemplateMeta` 模型含 name/description/style/version/author/variables/tags 字段，经过 Pydantic 校验
- [ ] `VariableDef` 模型含 name/type/description/required/default 字段，type 限制 str/int/float/bool
- [ ] `extract_variable_refs()` 正确提取 `{{ x }}`、`{% if x %}`、`{{ x|filter }}` 中的变量
- [ ] `_build_auto_meta()` 为无元数据模板自动生成 VariableDef（type=str, required=False）
- [ ] `TemplateRegistry.discover()` 发现内置 7 个内置模板
- [ ] `TemplateRegistry.get_template()` 按名称返回 TemplateInfo
- [ ] `TemplateRegistry.register()` 动态注册字符串模板
- [ ] `TemplateRegistry.add_path()` 外部路径增量扫描
- [ ] `TemplateRegistry.reload()` 保留 registered 模板，更新 builtin/external
- [ ] `InterpolationEngine.render()` 无 schema 时直接渲染 Jinja2
- [ ] `InterpolationEngine.render()` 有 schema 时校验 required 变量 + 类型转换 + 默认值
- [ ] `InterpolationEngine.render_safe()` 渲染失败返回空串，不抛异常
- [ ] `_coerce_value()` 正确处理 str/int/float/bool 四种类型转换
- [ ] `validate_html_structure()` 检测 DOCTYPE/html/head/body/title/style/meta charset/viewport
- [ ] `validate_variable_consistency()` 检测未声明变量的引用和未使用的声明
- [ ] `validate_template()` 组合结构 + 变量 + 渲染三层校验
- [ ] `agent.py` 的 `render_scene_html()` 不传 registry 参数时行为完全向后兼容
- [ ] `agent.py` 的 `render_scene_html(registry=...)` 走 schema-aware 渲染
- [ ] `agent.py` schema-aware 渲染失败时静默回退硬编码渲染
- [ ] `__init__.py` 导出所有新增公开接口
- [ ] 单元测试全部通过
- [ ] 回归测试全部通过

### 验收

- [registry 发现内置模板]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.registry import TemplateRegistry; r=TemplateRegistry(); c=r.discover(); print('count:', c); print('names:', [t.metadata.name for t in r.list_templates()])"` — count >= 7，names 包含 minimal/tech/story/cinematic/vibrant/elegant/dark）
- [registry 模板变量]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.registry import TemplateRegistry; r=TemplateRegistry(); r.discover(); t=r.get_template('minimal'); print([(v.name, v.type, v.required) for v in t.metadata.variables])"` — 输出变量列表，含 scene_title/scene_content/scene_subtitle/scene_index/total_scenes/duration，全部 type=str required=False）
- [registry 注册动态模板]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.registry import TemplateRegistry; from xianyu.html_scene.schema import TemplateMeta, VariableDef; r=TemplateRegistry(); r.register('custom', '{{ x }}', meta=TemplateMeta(name='custom', variables=[VariableDef(name='x', required=True)])); t=r.get_template('custom'); print(t.metadata.variables[0].name, t.metadata.variables[0].required)"` — 输出 `x True`）
- [interpolation 基础渲染]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.interpolation import InterpolationEngine; e=InterpolationEngine(); print(e.render('{{ name }}!', {'name':'World'}))"` — 输出 `World!`）
- [interpolation schema 校验]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.interpolation import InterpolationEngine; from xianyu.html_scene.schema import VariableDef; e=InterpolationEngine(); schema=[VariableDef(name='x', required=True)]; try: e.render('{{ x }}', {}, schema); except ValueError as ex: print('caught:', ex)"` — 输出 `caught: missing required: x`）
- [validation HTML 结构]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.validation import validate_html_structure; r=validate_html_structure('<!DOCTYPE html><html><head><meta charset=utf-8><title>T</title><style></style></head><body></body></html>'); print('valid:', r.is_valid, 'errors:', len(r.errors))"` — 输出 `valid: True errors: 0`）
- [validation 完整模板]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.registry import TemplateRegistry; from xianyu.html_scene.validation import validate_template; r=TemplateRegistry(); r.discover(); t=r.get_template('tech'); result=validate_template(t.content, meta=t.metadata, sample_variables={'scene_title':'T','scene_content':'C','scene_subtitle':'S','scene_index':1,'total_scenes':3,'duration':5.0}); print('valid:', result.is_valid, 'errors:', len(result.errors), 'warnings:', len(result.warnings))"` — 输出 `valid: True errors: 0 warnings: ...`）
- [agent 向后兼容]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.agent import render_scene_html; from xianyu.html_scene.schema import SceneDescription; s=SceneDescription(title='T', content='C', style='tech'); html=render_scene_html(s, 1, 3); print('T' in html)"` — 输出 `True`，与之前行为一致）
- [agent schema-aware 渲染]（参考：`cd ~/program/xianyu && uv run python -c "from xianyu.html_scene.agent import render_scene_html; from xianyu.html_scene.registry import TemplateRegistry; from xianyu.html_scene.schema import SceneDescription; r=TemplateRegistry(); r.discover(); s=SceneDescription(title='Hello World', content='Content', style='minimal'); html=render_scene_html(s, 1, 3, registry=r); print('Hello World' in html)"` — 输出 `True`）
- [单元测试]（参考：`cd ~/program/xianyu && uv run python -m pytest tests/html_scene/test_registry.py tests/html_scene/test_interpolation.py tests/html_scene/test_validation.py -q --tb=short -v` — 全部通过）
- [回归测试]（参考：`cd ~/program/xianyu && uv run python -m pytest tests/html_scene/ -q --tb=short -v` — 原有 test_schema.py + test_agent.py 以及新增测试全部通过）
- [类型检查]（参考：`cd ~/program/xianyu && uv run mypy src/xianyu/html_scene/registry.py src/xianyu/html_scene/interpolation.py src/xianyu/html_scene/validation.py --strict` — 0 errors）
- [总回归]（参考：`cd ~/program/xianyu && uv run python -m pytest tests/ -q --tb=short --ignore=tests/e2e --ignore=tests/integration` — 原有测试全部通过）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | TemplateRegistry + InterpolationEngine + Validation + schema 扩展 + agent 集成 + 单元测试 | `feat(html-scene): add template core system — registry, interpolation engine, validation (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（1）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. agent.py 完成 schema-aware 集成后，后续可支持模板声明自定义变量（如 `background_color`、`font_family`、`animation` 等），在 SceneDescription 中扩展额外字段
2. validation 的 HTML 结构检查目前基于正则匹配，后续可集成 html.parser 做更精准的标签嵌套校验
3. 为 templates/*.html 添加 `# @meta` 注释标记，使模板能在文件头声明自己的元数据（变量声明等），替代 registry 自动推断
4. 后续可增加 `xianyu html-scene validate` CLI 命令，对 templates/ 目录批量校验
