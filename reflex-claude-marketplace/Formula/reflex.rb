class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/reflex"
  url "https://github.com/neverprepared/reflex/releases/download/reflex/v0.0.1/reflex-0.0.1.tar.gz"
  sha256 "3f0cc0f1b0e3b9491ccfa8f6ed95d16590acc765260e1132e49a857fd021afce"
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
