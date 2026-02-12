class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/reflex"
  url "https://github.com/neverprepared/reflex/releases/download/reflex/v1.7.2/reflex-1.7.2.tar.gz"
  sha256 "PLACEHOLDER"
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
