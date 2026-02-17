# Template System for Profile Generation

## Overview

The shell-profiler now uses a Go template-based system for generating workspace profile configuration files. This provides better maintainability, consistency, and testability compared to the previous hardcoded string approach.

## Architecture

### Directory Structure

```
internal/templates/
├── README.md           # Documentation and usage guide
├── templates.go        # Template rendering functions
├── templates_test.go   # Unit tests
├── envrc.tpl          # Template for .envrc file
├── env.tpl            # Template for .env file
└── gitconfig.tpl      # Template for .gitconfig file
```

### Components

1. **Template Files (*.tpl)**: Text-based templates with Go template syntax
2. **Rendering Functions**: Go functions that parse and execute templates with data
3. **Data Structs**: Type-safe structures for template variables
4. **Unit Tests**: Comprehensive tests for each template

## Migration from Hardcoded Strings

### Before (create.go)

```go
func createEnvrc(profileDir string, opts CreateOptions) error {
    created := time.Now().UTC().Format("2006-01-02 15:04:05 UTC")

    envrcContent := fmt.Sprintf(`#!/usr/bin/env bash
# Workspace profile: %s
# Template: %s
# Created: %s
...
`, opts.ProfileName, opts.Template, created, opts.ProfileName)

    envrcPath := filepath.Join(profileDir, ".envrc")
    return os.WriteFile(envrcPath, []byte(envrcContent), 0644)
}
```

### After (create.go)

```go
func createEnvrc(profileDir string, opts CreateOptions) error {
    ui.PrintInfo("Creating .envrc...")

    envrcContent, err := templates.RenderEnvrc(opts.ProfileName, opts.Template)
    if err != nil {
        return fmt.Errorf("failed to render .envrc template: %w", err)
    }

    envrcPath := filepath.Join(profileDir, ".envrc")
    return os.WriteFile(envrcPath, []byte(envrcContent), 0644)
}
```

## Benefits

### 1. Maintainability

- **Single source of truth**: Template content lives in dedicated files
- **Version control**: Easy to see template changes in git diffs
- **Easier updates**: Modify templates without touching Go code
- **Separation of concerns**: Content vs. logic

### 2. Consistency

- **Uniform structure**: All profiles use identical templates
- **Fewer errors**: Template variables are type-checked at compile time
- **Enforced standards**: Templates ensure consistent formatting

### 3. Testability

- **Unit testable**: Each template has comprehensive tests
- **Isolated testing**: Test templates independently from business logic
- **Regression prevention**: Catch template errors before deployment

### 4. Flexibility

- **Conditional logic**: Use `{{if}}` for template-specific sections
- **Variable substitution**: Safe interpolation with `{{.VarName}}`
- **Reusability**: Share templates across commands (create, update)

## Templates Reference

### 1. envrc.tpl

**Purpose**: Generate `.envrc` file for direnv

**Variables**:
- `ProfileName` - Name of the workspace profile
- `Template` - Template type (basic, personal, work, client)
- `CreatedAt` - Timestamp when created

**Example**:
```bash
#!/usr/bin/env bash
# Workspace profile: {{.ProfileName}}
# Template: {{.Template}}
# Created: {{.CreatedAt}}

export WORKSPACE_PROFILE="{{.ProfileName}}"
export WORKSPACE_HOME="$PWD"
```

### 2. env.tpl

**Purpose**: Generate `.env` file with tool-specific environment variables

**Variables**:
- `ProfileName` - Name of the workspace profile
- `Template` - Template type

**Example**:
```bash
# Environment variables for workspace profile: {{.ProfileName}}
# Template: {{.Template}}

GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"
AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"
```

### 3. gitconfig.tpl

**Purpose**: Generate `.gitconfig` file with git settings

**Variables**:
- `ProfileName` - Name of the workspace profile
- `Template` - Template type
- `GitName` - Git user name
- `GitEmail` - Git user email

**Example**:
```ini
# Git configuration for workspace profile: {{.ProfileName}}
# Template: {{.Template}}

[user]
    name = {{.GitName}}
    email = {{.GitEmail}}

{{if eq .Template "work"}}
# Work-specific settings
[commit]
    gpgsign = true
{{end}}
```

## Adding New Templates

Follow these steps to add a new template:

### Step 1: Create Template File

Create a new `.tpl` file in `internal/templates/`:

```bash
# internal/templates/readme.tpl
# Workspace Profile: {{.ProfileName}}

Created: {{.CreatedAt}}
Template: {{.Template}}

## Quick Start

1. cd to this directory
2. Run `direnv allow`
3. Verify: `echo $WORKSPACE_PROFILE`
```

### Step 2: Add Embed Directive

In `templates.go`, add:

```go
//go:embed readme.tpl
var readmeTemplate string
```

### Step 3: Create Data Struct

```go
type ReadmeData struct {
    ProfileName string
    Template    string
    CreatedAt   string
}
```

### Step 4: Add Rendering Function

```go
func RenderReadme(profileName, templateType string) (string, error) {
    tmpl, err := template.New("readme").Parse(readmeTemplate)
    if err != nil {
        return "", fmt.Errorf("failed to parse readme template: %w", err)
    }

    data := ReadmeData{
        ProfileName: profileName,
        Template:    templateType,
        CreatedAt:   time.Now().UTC().Format("2006-01-02 15:04:05 UTC"),
    }

    var buf bytes.Buffer
    if err := tmpl.Execute(&buf, data); err != nil {
        return "", fmt.Errorf("failed to render readme template: %w", err)
    }

    return buf.String(), nil
}
```

### Step 5: Write Tests

In `templates_test.go`:

```go
func TestRenderReadme(t *testing.T) {
    tests := []struct {
        name         string
        profileName  string
        templateType string
        wantContains []string
    }{
        {
            name:         "basic readme",
            profileName:  "test-profile",
            templateType: "basic",
            wantContains: []string{
                "# Workspace Profile: test-profile",
                "Template: basic",
                "direnv allow",
            },
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := RenderReadme(tt.profileName, tt.templateType)
            if err != nil {
                t.Errorf("RenderReadme() error = %v", err)
                return
            }

            for _, want := range tt.wantContains {
                if !strings.Contains(got, want) {
                    t.Errorf("RenderReadme() missing: %q", want)
                }
            }
        })
    }
}
```

### Step 6: Use in Commands

In `create.go` or `update.go`:

```go
func createREADME(profileDir string, opts CreateOptions) error {
    ui.PrintInfo("Creating README.md...")

    content, err := templates.RenderReadme(opts.ProfileName, opts.Template)
    if err != nil {
        return fmt.Errorf("failed to render README template: %w", err)
    }

    readmePath := filepath.Join(profileDir, "README.md")
    return os.WriteFile(readmePath, []byte(content), 0644)
}
```

## Template Syntax Guide

### Variable Substitution

```go
{{.VariableName}}
```

### Conditionals

```go
{{if .Condition}}
    content when true
{{else}}
    content when false
{{end}}
```

### Equality Check

```go
{{if eq .Template "work"}}
    work-specific content
{{else if eq .Template "personal"}}
    personal-specific content
{{end}}
```

### Comments

```go
{{/* This is a template comment, not rendered */}}
```

### String Functions

```go
{{.ProfileName | lower}}  # Convert to lowercase
{{.ProfileName | upper}}  # Convert to uppercase
```

## Testing Strategy

### Unit Tests

Each template should have:

1. **Happy path test**: Verify basic rendering works
2. **Variable substitution test**: Check all variables are interpolated
3. **Conditional logic test**: Test all template branches
4. **Edge cases**: Empty values, special characters, etc.

### Integration Tests

Test the full workflow:

```go
func TestCreateProfileWithTemplates(t *testing.T) {
    // Setup temp directory
    tmpDir := t.TempDir()

    opts := CreateOptions{
        ProfileName: "test-profile",
        Template:    "work",
        GitName:     "Test User",
        GitEmail:    "test@example.com",
    }

    // Create profile
    err := CreateProfile(tmpDir, opts)
    if err != nil {
        t.Fatal(err)
    }

    // Verify files exist and have correct content
    envrcPath := filepath.Join(tmpDir, "test-profile", ".envrc")
    content, err := os.ReadFile(envrcPath)
    if err != nil {
        t.Fatal(err)
    }

    if !strings.Contains(string(content), "test-profile") {
        t.Error("Profile name not found in .envrc")
    }
}
```

## Troubleshooting

### Template Parsing Errors

**Error**: `failed to parse template: unexpected "}" in operand`

**Solution**: Check for unescaped `{` or `}` in template. Use `{{"{{"}}` to escape.

### Variable Not Interpolated

**Error**: Template renders `{{.VarName}}` literally

**Solution**: Ensure variable is defined in data struct and passed to `Execute()`.

### Conditional Not Working

**Error**: Wrong branch executed in `{{if}}`

**Solution**: Use `eq` for equality: `{{if eq .Template "work"}}`

## Performance Considerations

### Template Caching

Templates are embedded at compile time using `go:embed`, so there's no runtime file I/O.

### Rendering Speed

Template rendering is fast (< 1ms for typical templates). No caching needed.

## Migration Checklist

When migrating hardcoded strings to templates:

- [ ] Create `.tpl` file with template content
- [ ] Add `go:embed` directive in `templates.go`
- [ ] Create data struct for template variables
- [ ] Add rendering function
- [ ] Write comprehensive tests
- [ ] Update consuming code to use template
- [ ] Remove old hardcoded string
- [ ] Run all tests to verify
- [ ] Update documentation

## Future Enhancements

Potential improvements to the template system:

1. **Template validation**: Lint templates for common errors
2. **Hot reload**: Auto-reload templates during development
3. **Template functions**: Add custom template functions (e.g., `{{toSnakeCase .Name}}`)
4. **Partial templates**: Share common template fragments
5. **Template versioning**: Support multiple template versions for migration
6. **JSON/YAML templates**: Use structured formats instead of text

## References

- [Go text/template documentation](https://pkg.go.dev/text/template)
- [Go embed documentation](https://pkg.go.dev/embed)
- [Template best practices](https://go.dev/blog/template)

## Change Log

### 2024-02-16 - Initial Template System

- Created `internal/templates/` package
- Added templates for `.envrc`, `.env`, `.gitconfig`
- Migrated `createEnvrc()`, `createEnvFile()`, `createGitconfig()` to use templates
- Added comprehensive unit tests
- Updated `update.go` to use templates for consistency
- Created documentation and usage guide
