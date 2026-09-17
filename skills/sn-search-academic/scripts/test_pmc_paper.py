#!/usr/bin/env python3
"""
pmc_paper.py 回归测试。

覆盖：
  - 模块可正常导入（回归：defusedxml.ElementTree 无 Element 属性导致的导入期崩溃）
  - 正常 JATS XML 可被正确解析
  - 含外部实体（XXE）的 XML 会被 defusedxml 拒绝

运行：
  python3 test_pmc_paper.py
  python3 -m unittest test_pmc_paper
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pmc_paper  # noqa: E402
from defusedxml.common import EntitiesForbidden  # noqa: E402


class ImportTest(unittest.TestCase):
    def test_module_imports_without_error(self):
        import importlib

        importlib.reload(pmc_paper)


class XmlParsingTest(unittest.TestCase):
    SAFE_XML = """<?xml version="1.0"?>
<pmc-articleset>
  <article>
    <body>
      <sec>
        <title>Introduction</title>
        <p>Hello world.</p>
      </sec>
    </body>
  </article>
</pmc-articleset>"""

    XXE_XML = """<?xml version="1.0"?>
<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<pmc-articleset>
  <article>
    <body>
      <sec>
        <title>Introduction</title>
        <p>&xxe;</p>
      </sec>
    </body>
  </article>
</pmc-articleset>"""

    def test_safe_xml_is_parsed(self):
        root = pmc_paper.ET.fromstring(self.SAFE_XML)
        sections = pmc_paper.extract_all_sections(root)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["name"], "Introduction")
        self.assertIn("Hello world.", sections[0]["text"])

    def test_external_entity_is_rejected(self):
        with self.assertRaises(EntitiesForbidden):
            pmc_paper.ET.fromstring(self.XXE_XML)


if __name__ == "__main__":
    unittest.main()
