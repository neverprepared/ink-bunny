# Shell Profiler Templates

This directory contains Go templates for generating workspace profile configuration files.

## Template Files

| Template | Purpose | Variables |
|----------|---------|-----------|
| `envrc.tpl` | direnv configuration file | `ProfileName`, `Template`, `CreatedAt` |
| `env.tpl` | Environment variables for tools | `ProfileName`, `Template` |
| `gitconfig.tpl` | Git configuration | `ProfileName`, `Template`, `GitName`, `GitEmail` |

## Template Syntax

Templates use Go's `text/template` syntax:

```go
# Profile: {{.ProfileName}}
export WORKSPACE_PROFILE="{{.ProfileName}}"
```

### Conditionals

Templates support conditional logic based on the template type:

```go
{{if eq .Template "work"}}
# Work-specific settings
{{else if eq .Template "personal"}}
# Personal settings
{{end}}
```

## Adding New Templates

1. Create a new `.tpl` file in this directory
2. Add `//go:embed <filename>.tpl` to `templates.go`
3. Create a data struct if needed (e.g., `MyTemplateData`)
4. Add a `Render<Name>()` function to `templates.go`
5. Write tests in `templates_test.go`
6. Update the consuming code to use the new template

### Example

**1. Create template file (`ssh-config.tpl`):**

```
# SSH config for {{.ProfileName}}
Host github.com
    HostName github.com
    User git
    IdentityFile {{.SSHKeyPath}}
```

**2. Update `templates.go`:**

```go
//go:embed ssh-config.tpl
var sshConfigTemplate string

type SSHConfigData struct {
    ProfileName string
    SSHKeyPath  string
}

func RenderSSHConfig(profileName, sshKeyPath string) (string, error) {
    tmpl, err := template.New("ssh-config").Parse(sshConfigTemplate)
    if err != nil {
        return "", fmt.Errorf("failed to parse ssh-config template: %w", err)
    }

    data := SSHConfigData{
        ProfileName: profileName,
        SSHKeyPath:  sshKeyPath,
    }

    var buf bytes.Buffer
    if err := tmpl.Execute(&buf, data); err != nil {
        return "", fmt.Errorf("failed to render ssh-config template: %w", err)
    }

    return buf.String(), nil
}
```

**3. Write tests:**

```go
func TestRenderSSHConfig(t *testing.T) {
    got, err := RenderSSHConfig("test-profile", "/path/to/key")
    if err != nil {
        t.Fatal(err)
    }

    if !strings.Contains(got, "# SSH config for test-profile") {
        t.Error("missing profile name in header")
    }
}
```

**4. Use in commands:**

```go
func createSSHConfig(profileDir string, opts CreateOptions) error {
    content, err := templates.RenderSSHConfig(opts.ProfileName, "/path/to/key")
    if err != nil {
        return err
    }

    path := filepath.Join(profileDir, ".ssh/config")
    return os.WriteFile(path, []byte(content), 0600)
}
```

## Template Variables Reference

### Common Variables

- `ProfileName` - Name of the workspace profile
- `Template` - Template type (basic, personal, work, client)
- `CreatedAt` - Timestamp when the profile was created (RFC3339 format)

### Template-Specific Variables

#### envrc.tpl
- No additional variables

#### env.tpl
- No additional variables

#### gitconfig.tpl
- `GitName` - Git user name
- `GitEmail` - Git user email

## Testing

Run tests for all templates:

```bash
go test ./internal/templates/...
```

Run tests with verbose output:

```bash
go test -v ./internal/templates/...
```

## Design Principles

1. **Separation of Concerns**: Templates contain only markup and structure, not business logic
2. **Defaults**: Use sensible defaults in rendering functions when values are empty
3. **Validation**: Validate template syntax at compile time using `go:embed`
4. **Testing**: All templates must have test coverage
5. **Documentation**: Document all template variables and their purpose

## Benefits of Template System

### Maintainability
- Single source of truth for file structure
- Easy to update across all profiles
- Version control friendly

### Consistency
- All profiles use identical structure
- Reduces human error in manual file creation
- Enforces standards

### Flexibility
- Template conditionals for different profile types
- Easy to add new variables
- Supports custom rendering logic

### Testability
- Templates can be unit tested
- Rendering logic is isolated and testable
- Catches errors before runtime
