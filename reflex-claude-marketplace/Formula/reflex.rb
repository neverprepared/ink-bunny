class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/numa"
  url "https://github.com/neverprepared/numa/releases/download/reflex/v0.0.1/reflex-0.0.1.tar.gz"
  sha256 "1a6df92eba8fceef68392d15375eeac07d0131544b1b003cc46a2fbf96254c4c"
  license "MIT"

  def install
    (share/"reflex/plugins/reflex").install Dir["plugins/reflex/*"]
  end

  def caveats
    <<~EOS
      To use reflex with Claude Code:

        claude --plugin-dir #{share}/reflex

      Or install from the plugin marketplace:

        /plugin marketplace add mindmorass/reflex
    EOS
  end

  test do
    assert_predicate share/"reflex/plugins/reflex/.claude-plugin/plugin.json", :exist?
  end
end
