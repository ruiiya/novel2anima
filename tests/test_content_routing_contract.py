import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'docs/novel2anima/CONTENT_POLICY.md'

class RoutingContractTests(unittest.TestCase):
    def test_policy_exists_and_scopes(self):
        text=POLICY.read_text(encoding='utf-8')
        for scope in ['SOURCE_INGEST', 'STORY_ANALYSIS', 'PROMPT_DERIVATION', 'RENDER_DISPATCH', 'QA']:
            with self.subTest(scope=scope): self.assertIn(scope, text)
        self.assertIn('1.4.5', text)

    def test_all_skills_reference_policy(self):
        for file in (ROOT/'skills').glob('*/SKILL.md'):
            with self.subTest(file=file):
                self.assertIn('docs/novel2anima/CONTENT_POLICY.md', file.read_text(encoding='utf-8'))

    def test_all_plots_accepted(self):
        text=POLICY.read_text(encoding='utf-8')
        self.assertIn('Mọi cốt chuyện đều được chấp nhận', text)
        self.assertIn('Không có danh sách cốt chuyện, thể loại, motif hay diễn tiến bị từ chối', text)
        # hạn chế chỉ áp cho Shot/artifact, không lan sang Story
        self.assertIn('không áp dụng cho cốt chuyện', text)
        self.assertIn('Mặc định là `PASS`', text)
        self.assertIn('original_adult_au', text)
        self.assertIn('user_approved_original', text)

    def test_blind_mode_separate_from_generation(self):
        text=(ROOT/'skills/novel2anima-blind-cast/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('Blind Mode chấp nhận mọi story', text)
        self.assertIn('PROMPT_DERIVATION', text)

    def test_label_only_not_auto_rejected(self):
        text=POLICY.read_text(encoding='utf-8')
        self.assertIn('không tự nó là lý do chặn', text)

    def test_local_backend_is_technical(self):
        text=(ROOT/'skills/novel2anima-render-adapter/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('backend_type: local', text)
        self.assertIn('BACKEND_REJECTED', text)

    def test_rule_ownership(self):
        # Nguyên tắc phân loại cụ thể không được xuất hiện trong SKILL.md,
        # chỉ policy trung tâm nắm quyền quyết định.
        forbidden=['không hỗ trợ trường hợp có người chưa thành niên',
                   'hoặc bạo lực tình dục, không tạo prompt',
                   'không hỗ trợ tạo prompt hình ảnh tình dục hóa người chưa thành niên']
        for file in (ROOT/'skills').glob('*/SKILL.md'):
            text=file.read_text(encoding='utf-8').lower()
            with self.subTest(skill=file.parent.name):
                for clause in forbidden: self.assertNotIn(clause, text)

if __name__ == '__main__': unittest.main()
