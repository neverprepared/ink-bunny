# Git configuration for workspace profile: {{.ProfileName}}
# Template: {{.Template}}

[user]
    name = {{.GitName}}
    email = {{.GitEmail}}

[core]
    editor = vim
    autocrlf = input
    whitespace = trailing-space,space-before-tab

[init]
    defaultBranch = main

[push]
    default = current
    autoSetupRemote = true

[pull]
    rebase = false

[fetch]
    prune = true

[merge]
    conflictstyle = diff3

[rebase]
    autoStash = true
    autoSquash = true

[diff]
    algorithm = histogram
    colorMoved = default

[log]
    abbrevCommit = true
    date = iso

[color]
    ui = auto

[alias]
    st = status -sb
    lg = log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
    br = branch -v
    co = checkout
    ci = commit
    cm = commit -m
    amend = commit --amend --no-edit
    last = log -1 HEAD --stat
    undo = reset HEAD~1 --mixed
    aliases = config --get-regexp alias
{{if eq .Template "personal"}}
# Personal project settings
[commit]
    verbose = true

[credential]
    helper = cache --timeout=3600
{{else if eq .Template "work"}}
# Work project settings
[commit]
    verbose = true
    # Uncomment to enable GPG signing
    # gpgsign = true

[credential]
    helper = cache --timeout=7200
{{else if eq .Template "client"}}
# Client project settings
[commit]
    verbose = true
    # gpgsign = true

[credential]
    helper = cache --timeout=3600
{{end}}
