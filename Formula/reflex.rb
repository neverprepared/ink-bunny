class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex-v1.18.0/reflex-1.18.0.tar.gz"
  sha256 "df9b8d3ea284e299fcf393dfe4c905c543e82e2ea530c817aab2bc38fe378049"
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
    assert_path_exists share/"reflex/.claude-plugin/plugin.json"
  end
end
