class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex-v1.17.0/reflex-1.17.0.tar.gz"
  sha256 "ea721816f57918e68170253f761aff7b841625566e50f5b67e29a64acfbdf6d0"
  license "MIT"

  def install
    (share/"reflex").install Dir["plugins/reflex/*"]
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
    assert_predicate share/"reflex/.claude-plugin/plugin.json", :exist?
  end
end
