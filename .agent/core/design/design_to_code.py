#!/usr/bin/env python3
"""
Design-to-Code Engine.

Generates production-ready code from design specifications.

Supports:
- React (with TypeScript)
- Vue 3 (Composition API)
- Svelte
- HTML/CSS
- React Native

Styling:
- Tailwind CSS
- CSS Modules
- Styled Components
- SCSS

Version: 1.0.0
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("design-to-code")


class Framework(Enum):
    """Supported frameworks."""

    REACT = "react"
    REACT_NATIVE = "react-native"
    VUE = "vue"
    SVELTE = "svelte"
    HTML = "html"


class StylingApproach(Enum):
    """Supported styling approaches."""

    TAILWIND = "tailwind"
    CSS_MODULES = "css-modules"
    STYLED_COMPONENTS = "styled-components"
    SCSS = "scss"
    INLINE = "inline"


class ComponentType(Enum):
    """Component types."""

    ATOM = "atom"
    MOLECULE = "molecule"
    ORGANISM = "organism"
    TEMPLATE = "template"
    PAGE = "page"


@dataclass
class DesignToken:
    """A design token."""

    name: str
    value: str
    category: str
    description: str | None = None


@dataclass
class ComponentSpec:
    """Specification for a component."""

    name: str
    type: ComponentType
    description: str
    props: list[dict]
    variants: list[str]
    states: list[str]
    children: list[str] | None = None
    accessibility: dict = field(default_factory=dict)
    responsive: dict = field(default_factory=dict)
    tokens_used: list[str] = field(default_factory=list)


@dataclass
class GeneratedCode:
    """Generated code output."""

    component_name: str
    framework: Framework
    styling: StylingApproach
    files: dict[str, str]  # filename -> content
    dependencies: list[str]
    instructions: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "component_name": self.component_name,
            "framework": self.framework.value,
            "styling": self.styling.value,
            "files": self.files,
            "dependencies": self.dependencies,
            "instructions": self.instructions,
            "timestamp": self.timestamp.isoformat(),
        }


class DesignToCodeEngine:
    """
    Converts design specifications to production-ready code.

    Features:
    - Multi-framework support
    - Proper TypeScript types
    - Accessibility built-in
    - Responsive by default
    - Test generation
    """

    def __init__(
        self,
        framework: Framework = Framework.REACT,
        styling: StylingApproach = StylingApproach.TAILWIND,
    ):
        self.framework = framework
        self.styling = styling
        self.tokens: dict[str, DesignToken] = {}

    def load_tokens(self, tokens: dict[str, Any]):
        """Load design tokens."""
        for category, values in tokens.items():
            if isinstance(values, dict):
                for name, value in values.items():
                    token_name = f"{category}-{name}"
                    self.tokens[token_name] = DesignToken(
                        name=token_name, value=str(value), category=category
                    )
        logger.info(f"Loaded {len(self.tokens)} design tokens")

    def generate_component(self, spec: ComponentSpec) -> GeneratedCode:
        """
        Generate code for a component.

        Args:
            spec: Component specification

        Returns:
            Generated code with all files
        """
        if self.framework == Framework.REACT:
            return self._generate_react(spec)
        elif self.framework == Framework.VUE:
            return self._generate_vue(spec)
        elif self.framework == Framework.SVELTE:
            return self._generate_svelte(spec)
        elif self.framework == Framework.HTML:
            return self._generate_html(spec)
        elif self.framework == Framework.REACT_NATIVE:
            return self._generate_react_native(spec)
        else:
            raise ValueError(f"Unsupported framework: {self.framework}")

    def _generate_react(self, spec: ComponentSpec) -> GeneratedCode:
        """Generate React component."""
        component_name = self._to_pascal_case(spec.name)
        files = {}

        # Generate TypeScript types
        types_content = self._generate_react_types(spec, component_name)

        # Generate component
        component_content = self._generate_react_component(spec, component_name)

        # Generate styles
        styles_content = self._generate_styles(spec)

        # Generate tests
        test_content = self._generate_react_tests(spec, component_name)

        # Generate stories (Storybook)
        stories_content = self._generate_storybook(spec, component_name)

        files[f"{component_name}.tsx"] = component_content
        files[f"{component_name}.types.ts"] = types_content
        files[f"{component_name}.test.tsx"] = test_content
        files[f"{component_name}.stories.tsx"] = stories_content

        if self.styling == StylingApproach.CSS_MODULES:
            files[f"{component_name}.module.css"] = styles_content
        elif self.styling == StylingApproach.SCSS:
            files[f"{component_name}.module.scss"] = styles_content

        # Index file
        files["index.ts"] = (
            f'export {{ {component_name} }} from "./{component_name}";\nexport type {{ {component_name}Props }} from "./{component_name}.types";\n'
        )

        dependencies = ["react", "@types/react"]
        if self.styling == StylingApproach.TAILWIND:
            dependencies.append("tailwindcss")
        elif self.styling == StylingApproach.STYLED_COMPONENTS:
            dependencies.extend(["styled-components", "@types/styled-components"])

        instructions = f"""
## {component_name} Component

### Installation
```bash
npm install {" ".join(dependencies)}
```

### Usage
```tsx
import {{ {component_name} }} from './components/{component_name}';

<{component_name} variant="primary" />
```

### Props
{self._format_props_table(spec.props)}

### Variants
{", ".join(spec.variants)}

### States
{", ".join(spec.states)}
"""

        return GeneratedCode(
            component_name=component_name,
            framework=self.framework,
            styling=self.styling,
            files=files,
            dependencies=dependencies,
            instructions=instructions,
        )

    def _generate_react_types(self, spec: ComponentSpec, name: str) -> str:
        """Generate TypeScript types for React component."""
        props_interface = []
        for prop in spec.props:
            prop_type = prop.get("type", "string")
            required = prop.get("required", False)
            description = prop.get("description", "")
            optional = "" if required else "?"
            props_interface.append(
                f"  /** {description} */\n  {prop['name']}{optional}: {prop_type};"
            )

        variants_type = " | ".join(f'"{v}"' for v in spec.variants) if spec.variants else "string"

        return f"""import {{ ComponentPropsWithoutRef, ReactNode }} from 'react';

/**
 * Variant options for {name}
 */
export type {name}Variant = {variants_type};

/**
 * Props for {name} component
 */
export interface {name}Props extends ComponentPropsWithoutRef<'div'> {{
{chr(10).join(props_interface)}
  /** Visual variant */
  variant?: {name}Variant;
  /** Component children */
  children?: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  isLoading?: boolean;
}}
"""

    def _generate_react_component(self, spec: ComponentSpec, name: str) -> str:
        """Generate React component."""
        # Generate class names based on styling approach
        if self.styling == StylingApproach.TAILWIND:
            base_classes = self._generate_tailwind_classes(spec)
            style_import = ""
            class_logic = f'''
  const baseClasses = "{base_classes}";
  const variantClasses = {{
{self._generate_variant_classes(spec.variants)}
  }};
  const classes = cn(baseClasses, variantClasses[variant], className);'''
        else:
            style_import = f'import styles from "./{name}.module.css";'
            class_logic = f"""
  const classes = cn(
    styles.{self._to_camel_case(name)},
    styles[variant],
    {{ [styles.disabled]: disabled }},
    className
  );"""

        # Generate accessibility attributes
        a11y_attrs = self._generate_a11y_attributes(spec)

        return f"""import {{ forwardRef }} from 'react';
import {{ cn }} from '@/lib/utils';
import type {{ {name}Props }} from './{name}.types';
{style_import}

/**
 * {spec.description}
 *
 * @example
 * ```tsx
 * <{name} variant="primary">Click me</{name}>
 * ```
 */
export const {name} = forwardRef<HTMLDivElement, {name}Props>(
  ({{ variant = 'primary', children, className, disabled, isLoading, ...props }}, ref) => {{
{class_logic}

    return (
      <div
        ref={{ref}}
        className={{classes}}
        {a11y_attrs}
        {{...props}}
      >
        {{isLoading ? (
          <span className="animate-spin">⏳</span>
        ) : (
          children
        )}}
      </div>
    );
  }}
);

{name}.displayName = '{name}';
"""

    def _generate_react_tests(self, spec: ComponentSpec, name: str) -> str:
        """Generate React tests."""
        return f"""import {{ render, screen, fireEvent }} from '@testing-library/react';
import {{ axe, toHaveNoViolations }} from 'jest-axe';
import {{ {name} }} from './{name}';

expect.extend(toHaveNoViolations);

describe('{name}', () => {{
  // Rendering tests
  it('renders without crashing', () => {{
    render(<{name}>Test</{name}>);
    expect(screen.getByText('Test')).toBeInTheDocument();
  }});

  // Variant tests
{self._generate_variant_tests(spec.variants, name)}

  // State tests
  it('handles disabled state', () => {{
    render(<{name} disabled>Disabled</{name}>);
    const element = screen.getByText('Disabled');
    expect(element).toHaveAttribute('aria-disabled', 'true');
  }});

  it('handles loading state', () => {{
    render(<{name} isLoading>Loading</{name}>);
    expect(screen.getByText('⏳')).toBeInTheDocument();
  }});

  // Accessibility tests
  it('has no accessibility violations', async () => {{
    const {{ container }} = render(<{name}>Accessible</{name}>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  }});

  // Interaction tests
  it('handles click events', () => {{
    const handleClick = jest.fn();
    render(<{name} onClick={{handleClick}}>Click me</{name}>);
    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  }});

  // Keyboard navigation
  it('is keyboard accessible', () => {{
    render(<{name} tabIndex={{0}}>Focusable</{name}>);
    const element = screen.getByText('Focusable');
    element.focus();
    expect(element).toHaveFocus();
  }});
}});
"""

    def _generate_storybook(self, spec: ComponentSpec, name: str) -> str:
        """Generate Storybook stories."""
        variant_stories = "\n".join(
            [
                f"""
export const {self._to_pascal_case(v)}: Story = {{
  args: {{
    variant: '{v}',
    children: '{v.title()} Variant',
  }},
}};"""
                for v in spec.variants
            ]
        )

        return f"""import type {{ Meta, StoryObj }} from '@storybook/react';
import {{ {name} }} from './{name}';

const meta: Meta<typeof {name}> = {{
  title: 'Components/{name}',
  component: {name},
  tags: ['autodocs'],
  argTypes: {{
    variant: {{
      control: 'select',
      options: {spec.variants},
    }},
    disabled: {{
      control: 'boolean',
    }},
    isLoading: {{
      control: 'boolean',
    }},
  }},
}};

export default meta;
type Story = StoryObj<typeof {name}>;

export const Default: Story = {{
  args: {{
    children: '{name} Component',
  }},
}};
{variant_stories}

export const Disabled: Story = {{
  args: {{
    children: 'Disabled {name}',
    disabled: true,
  }},
}};

export const Loading: Story = {{
  args: {{
    children: 'Loading {name}',
    isLoading: true,
  }},
}};

export const AllVariants: Story = {{
  render: () => (
    <div className="flex flex-col gap-4">
      {chr(10).join([f'      <{name} variant="{v}">{v.title()}</{name}>' for v in spec.variants])}
    </div>
  ),
}};
"""

    def _generate_vue(self, spec: ComponentSpec) -> GeneratedCode:
        """Generate Vue 3 component."""
        component_name = self._to_pascal_case(spec.name)
        files = {}

        # Generate Vue SFC
        vue_content = self._generate_vue_sfc(spec, component_name)
        files[f"{component_name}.vue"] = vue_content

        # Generate tests
        test_content = self._generate_vue_tests(spec, component_name)
        files[f"{component_name}.spec.ts"] = test_content

        dependencies = ["vue"]
        if self.styling == StylingApproach.TAILWIND:
            dependencies.append("tailwindcss")

        instructions = f"""
## {component_name} Component (Vue 3)

### Usage
```vue
<script setup>
import {component_name} from './components/{component_name}.vue';
</script>

<template>
  <{component_name} variant="primary" />
</template>
```
"""

        return GeneratedCode(
            component_name=component_name,
            framework=self.framework,
            styling=self.styling,
            files=files,
            dependencies=dependencies,
            instructions=instructions,
        )

    def _generate_vue_sfc(self, spec: ComponentSpec, name: str) -> str:
        """Generate Vue Single File Component."""
        ", ".join(
            [
                f"{p['name']}: {{ type: {self._ts_to_vue_type(p.get('type', 'string'))}, default: {p.get('default', 'undefined')} }}"
                for p in spec.props
            ]
        )

        return f"""<script setup lang="ts">
import {{ computed }} from 'vue';

interface Props {{
  variant?: {" | ".join(f"'{v}'" for v in spec.variants)};
  disabled?: boolean;
  isLoading?: boolean;
}}

const props = withDefaults(defineProps<Props>(), {{
  variant: 'primary',
  disabled: false,
  isLoading: false,
}});

const emit = defineEmits<{{
  (e: 'click', event: MouseEvent): void;
}}>();

const classes = computed(() => [
  'base-classes',
  `variant-${{props.variant}}`,
  {{ 'is-disabled': props.disabled }},
  {{ 'is-loading': props.isLoading }},
]);
</script>

<template>
  <div
    :class="classes"
    :aria-disabled="disabled"
    @click="emit('click', $event)"
  >
    <span v-if="isLoading" class="animate-spin">⏳</span>
    <slot v-else />
  </div>
</template>

<style scoped>
{self._generate_styles(spec)}
</style>
"""

    def _generate_vue_tests(self, spec: ComponentSpec, name: str) -> str:
        """Generate Vue tests."""
        return f"""import {{ mount }} from '@vue/test-utils';
import {{ describe, it, expect }} from 'vitest';
import {name} from './{name}.vue';

describe('{name}', () => {{
  it('renders properly', () => {{
    const wrapper = mount({name}, {{
      slots: {{ default: 'Test' }},
    }});
    expect(wrapper.text()).toContain('Test');
  }});

  it('applies variant classes', () => {{
    const wrapper = mount({name}, {{
      props: {{ variant: 'primary' }},
    }});
    expect(wrapper.classes()).toContain('variant-primary');
  }});

  it('handles disabled state', () => {{
    const wrapper = mount({name}, {{
      props: {{ disabled: true }},
    }});
    expect(wrapper.attributes('aria-disabled')).toBe('true');
  }});

  it('emits click event', async () => {{
    const wrapper = mount({name});
    await wrapper.trigger('click');
    expect(wrapper.emitted('click')).toBeTruthy();
  }});
}});
"""

    def _generate_svelte(self, spec: ComponentSpec) -> GeneratedCode:
        """Generate Svelte component."""
        component_name = self._to_pascal_case(spec.name)
        files = {}

        svelte_content = f"""<script lang="ts">
  export let variant: {" | ".join(f"'{v}'" for v in spec.variants)} = 'primary';
  export let disabled = false;
  export let isLoading = false;

  $: classes = [
    'base',
    `variant-${{variant}}`,
    disabled && 'disabled',
    isLoading && 'loading',
  ].filter(Boolean).join(' ');
</script>

<div
  class={{classes}}
  aria-disabled={{disabled}}
  on:click
>
  {{#if isLoading}}
    <span class="animate-spin">⏳</span>
  {{:else}}
    <slot />
  {{/if}}
</div>

<style>
{self._generate_styles(spec)}
</style>
"""
        files[f"{component_name}.svelte"] = svelte_content

        return GeneratedCode(
            component_name=component_name,
            framework=self.framework,
            styling=self.styling,
            files=files,
            dependencies=["svelte"],
            instructions=f"## {component_name} (Svelte)\n\nImport and use as `<{component_name} />`",
        )

    def _generate_html(self, spec: ComponentSpec) -> GeneratedCode:
        """Generate plain HTML/CSS."""
        component_name = self._to_kebab_case(spec.name)
        files = {}

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{spec.name}</title>
  <link rel="stylesheet" href="{component_name}.css">
</head>
<body>
  <!-- {spec.description} -->
  <div class="{component_name}" role="button" tabindex="0">
    {spec.name}
  </div>

  <!-- Variants -->
{chr(10).join([f'  <div class="{component_name} {component_name}--{v}">{v.title()}</div>' for v in spec.variants])}
</body>
</html>
'''
        files[f"{component_name}.html"] = html_content
        files[f"{component_name}.css"] = self._generate_styles(spec)

        return GeneratedCode(
            component_name=component_name,
            framework=self.framework,
            styling=self.styling,
            files=files,
            dependencies=[],
            instructions=f"## {spec.name} (HTML/CSS)\n\nOpen {component_name}.html in a browser.",
        )

    def _generate_react_native(self, spec: ComponentSpec) -> GeneratedCode:
        """Generate React Native component."""
        component_name = self._to_pascal_case(spec.name)
        files = {}

        rn_content = f"""import React from 'react';
import {{ View, Text, Pressable, StyleSheet, ActivityIndicator }} from 'react-native';

interface {component_name}Props {{
  variant?: {" | ".join(f"'{v}'" for v in spec.variants)};
  disabled?: boolean;
  isLoading?: boolean;
  onPress?: () => void;
  children?: React.ReactNode;
}}

export const {component_name}: React.FC<{component_name}Props> = ({{
  variant = 'primary',
  disabled = false,
  isLoading = false,
  onPress,
  children,
}}) => {{
  return (
    <Pressable
      style={{[styles.base, styles[variant], disabled && styles.disabled]}}
      onPress={{onPress}}
      disabled={{disabled || isLoading}}
      accessibilityRole="button"
      accessibilityState={{{{ disabled }}}}
    >
      {{isLoading ? (
        <ActivityIndicator color="#fff" />
      ) : (
        <Text style={{styles.text}}>{{children}}</Text>
      )}}
    </Pressable>
  );
}};

const styles = StyleSheet.create({{
  base: {{
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  }},
{self._generate_rn_variant_styles(spec.variants)}
  disabled: {{
    opacity: 0.5,
  }},
  text: {{
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  }},
}});
"""
        files[f"{component_name}.tsx"] = rn_content

        return GeneratedCode(
            component_name=component_name,
            framework=self.framework,
            styling=StylingApproach.INLINE,
            files=files,
            dependencies=["react-native"],
            instructions=f"## {component_name} (React Native)\n\nImport from './{component_name}'",
        )

    # Helper methods
    def _generate_tailwind_classes(self, spec: ComponentSpec) -> str:
        """Generate Tailwind CSS classes."""
        return "flex items-center justify-center px-4 py-2 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2"

    def _generate_variant_classes(self, variants: list[str]) -> str:
        """Generate variant class mappings."""
        variant_styles = {
            "primary": '"bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500"',
            "secondary": '"bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500"',
            "outline": '"border-2 border-gray-300 bg-transparent hover:bg-gray-50 focus:ring-gray-500"',
            "ghost": '"bg-transparent hover:bg-gray-100 focus:ring-gray-500"',
            "destructive": '"bg-red-600 text-white hover:bg-red-700 focus:ring-red-500"',
        }
        lines = []
        for v in variants:
            style = variant_styles.get(v, '"bg-gray-500 text-white"')
            lines.append(f"    {v}: {style},")
        return "\n".join(lines)

    def _generate_variant_tests(self, variants: list[str], name: str) -> str:
        """Generate tests for each variant."""
        tests = []
        for v in variants:
            tests.append(f'''
  it('renders {v} variant', () => {{
    render(<{name} variant="{v}">Test</{name}>);
    expect(screen.getByText('Test')).toBeInTheDocument();
  }});''')
        return "\n".join(tests)

    def _generate_styles(self, spec: ComponentSpec) -> str:
        """Generate CSS styles."""
        name = self._to_kebab_case(spec.name)
        styles = [
            f".{name} {{",
            "  display: flex;",
            "  align-items: center;",
            "  justify-content: center;",
            "  padding: 0.5rem 1rem;",
            "  border-radius: 0.5rem;",
            "  font-weight: 500;",
            "  transition: all 0.2s;",
            "}",
        ]

        for v in spec.variants:
            styles.append(f"\n.{name}--{v} {{")
            if v == "primary":
                styles.extend(["  background-color: #3b82f6;", "  color: white;"])
            elif v == "secondary":
                styles.extend(["  background-color: #e5e7eb;", "  color: #1f2937;"])
            styles.append("}")

        return "\n".join(styles)

    def _generate_a11y_attributes(self, spec: ComponentSpec) -> str:
        """Generate accessibility attributes."""
        attrs = []
        a11y = spec.accessibility

        if a11y.get("role"):
            attrs.append(f'role="{a11y["role"]}"')
        if "aria-label" in a11y:
            attrs.append('aria-label={props["aria-label"]}')

        attrs.append("aria-disabled={disabled}")
        attrs.append("tabIndex={disabled ? -1 : 0}")

        return "\n        ".join(attrs)

    def _generate_rn_variant_styles(self, variants: list[str]) -> str:
        """Generate React Native variant styles."""
        styles = []
        colors = {
            "primary": "#3b82f6",
            "secondary": "#6b7280",
            "outline": "transparent",
            "ghost": "transparent",
            "destructive": "#ef4444",
        }
        for v in variants:
            color = colors.get(v, "#3b82f6")
            styles.append(f"  {v}: {{ backgroundColor: '{color}' }},")
        return "\n".join(styles)

    def _to_pascal_case(self, s: str) -> str:
        """Convert to PascalCase."""
        return "".join(word.capitalize() for word in re.split(r"[-_\s]", s))

    def _to_camel_case(self, s: str) -> str:
        """Convert to camelCase."""
        pascal = self._to_pascal_case(s)
        return pascal[0].lower() + pascal[1:] if pascal else ""

    def _to_kebab_case(self, s: str) -> str:
        """Convert to kebab-case."""
        return re.sub(r"(?<!^)(?=[A-Z])", "-", s).lower().replace("_", "-").replace(" ", "-")

    def _ts_to_vue_type(self, ts_type: str) -> str:
        """Convert TypeScript type to Vue prop type."""
        mapping = {
            "string": "String",
            "number": "Number",
            "boolean": "Boolean",
            "object": "Object",
            "array": "Array",
        }
        return mapping.get(ts_type.lower(), "String")

    def _format_props_table(self, props: list[dict]) -> str:
        """Format props as markdown table."""
        if not props:
            return "No additional props."

        lines = [
            "| Prop | Type | Default | Description |",
            "|------|------|---------|-------------|",
        ]
        for p in props:
            lines.append(
                f"| {p.get('name', '')} | {p.get('type', 'string')} | {p.get('default', '-')} | {p.get('description', '')} |"
            )
        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def generate_react_component(spec: dict, styling: str = "tailwind") -> GeneratedCode:
    """Quick generate React component."""
    engine = DesignToCodeEngine(framework=Framework.REACT, styling=StylingApproach(styling))
    component_spec = ComponentSpec(**spec)
    return engine.generate_component(component_spec)


def generate_vue_component(spec: dict) -> GeneratedCode:
    """Quick generate Vue component."""
    engine = DesignToCodeEngine(framework=Framework.VUE)
    component_spec = ComponentSpec(**spec)
    return engine.generate_component(component_spec)


def generate_from_design_system(
    design_system: dict, framework: str = "react"
) -> dict[str, GeneratedCode]:
    """Generate all components from a design system."""
    engine = DesignToCodeEngine(framework=Framework(framework))

    if "tokens" in design_system:
        engine.load_tokens(design_system["tokens"])

    results = {}
    for component in design_system.get("components", []):
        spec = ComponentSpec(**component)
        results[spec.name] = engine.generate_component(spec)

    return results


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Design-to-Code Engine")
    parser.add_argument("--spec", help="Path to component spec JSON")
    parser.add_argument(
        "--framework", choices=["react", "vue", "svelte", "html", "react-native"], default="react"
    )
    parser.add_argument(
        "--styling",
        choices=["tailwind", "css-modules", "styled-components", "scss"],
        default="tailwind",
    )
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--demo", action="store_true", help="Generate demo component")
    args = parser.parse_args()

    if args.demo:
        spec = ComponentSpec(
            name="button",
            type=ComponentType.ATOM,
            description="A versatile button component",
            props=[
                {
                    "name": "size",
                    "type": "'sm' | 'md' | 'lg'",
                    "default": "'md'",
                    "description": "Button size",
                }
            ],
            variants=["primary", "secondary", "outline", "ghost", "destructive"],
            states=["default", "hover", "active", "focus", "disabled", "loading"],
            accessibility={"role": "button"},
        )

        engine = DesignToCodeEngine(
            framework=Framework(args.framework), styling=StylingApproach(args.styling)
        )
        result = engine.generate_component(spec)

        print(f"\n=== Generated {result.component_name} ({result.framework.value}) ===\n")
        for filename, content in result.files.items():
            print(f"--- {filename} ---")
            print(content[:500] + "..." if len(content) > 500 else content)
            print()

        print(result.instructions)

    elif args.spec:
        with open(args.spec, encoding="utf-8") as f:
            spec_data = json.load(f)

        spec = ComponentSpec(**spec_data)
        engine = DesignToCodeEngine(
            framework=Framework(args.framework), styling=StylingApproach(args.styling)
        )
        result = engine.generate_component(spec)

        if args.output:
            from pathlib import Path

            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in result.files.items():
                (output_dir / filename).write_text(content)
            print(f"Generated {len(result.files)} files in {args.output}")
        else:
            print(json.dumps(result.to_dict(), indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
