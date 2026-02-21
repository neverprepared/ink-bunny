class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex-v1.12.0/reflex-1.12.0.tar.gz"
  sha256 "9b433a4f5eac8229c0b46c85c2d46fd577fa6b235bf0e5765e4803fa6d7bf2bf"
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
