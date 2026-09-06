from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/m4b-implement-and-verify-v6.yml")


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    docs_marker = "      - name: Rebind changed inherited-content evidence\n"
    docs_step = """      - name: Document all packaged Skill-only Memory examples
        shell: python
        run: |
          from pathlib import Path

          examples = (
              'assets/memory-policy.disabled.example.yaml',
              'assets/memory-policy.reviewed.example.yaml',
              'assets/memory-policy.automatic.example.json',
          )
          pages = {
              'site/src/content/docs/guides/downloads.md': (
                  '## Packaged Memory Policy examples',
                  'The Skill-only package also includes these opt-in configuration examples:',
                  'They are examples, not permission grants. Skill-only remains `skill-only-fallback` and cannot provide durable Memory by itself.',
              ),
              'site/src/content/docs/guides/install-skill.md': (
                  '## Packaged Memory Policy examples',
                  'The extracted Skill directory also contains:',
                  'These examples do not enable Memory automatically. Durable Memory requires the Plugin/Core runtime and an explicit Personal Policy.',
              ),
              'site/src/content/docs/zh-tw/guides/downloads.md': (
                  '## 套件內的 Memory Policy 範例',
                  '純 SKILL 套件也包含以下 opt-in 設定範例：',
                  '這些檔案只是範例，不代表授權。純 SKILL 仍是 `skill-only-fallback`，本身不提供可持久化的 Memory。',
              ),
              'site/src/content/docs/zh-tw/guides/install-skill.md': (
                  '## 套件內的 Memory Policy 範例',
                  '解壓縮後的 Skill 目錄也包含：',
                  '這些範例不會自動開啟 Memory。可持久化 Memory 仍需要 Plugin/Core runtime，以及使用者明確設定的 Personal Policy。',
              ),
          }
          for relative, (heading, intro, boundary) in pages.items():
              path = Path(relative)
              body = path.read_text('utf-8').rstrip()
              if all(example in body for example in examples):
                  continue
              section = [heading, '', intro, '']
              section.extend(f'- `{example}`' for example in examples)
              section.extend(['', boundary])
              path.write_text(body + '\\n\\n' + '\\n'.join(section) + '\\n', encoding='utf-8', newline='\\n')

"""
    if docs_step not in text:
        if docs_marker not in text:
            raise SystemExit("M4-B documentation insertion marker missing")
        text = text.replace(docs_marker, docs_step + docs_marker, 1)

    suite_marker = "      - name: Run complete Core and repository suites\n"
    dependency_step = """      - name: Install locked Plugin dependencies before repository reproducibility tests
        working-directory: plugins/workflow-skill-router
        run: npm ci

"""
    if dependency_step not in text:
        if suite_marker not in text:
            raise SystemExit("M4-B suite insertion marker missing")
        text = text.replace(suite_marker, dependency_step + suite_marker, 1)

    WORKFLOW.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
