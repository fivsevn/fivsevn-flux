"""Run real navigation JavaScript with deterministic browser event/layout doubles."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
JSC = Path('/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc')
ENGINE = shutil.which('node') or (str(JSC) if JSC.is_file() else None)


@unittest.skipUnless(ENGINE, 'Node or system JavaScriptCore is needed for browser logic regression checks')
class NavigationTests(unittest.TestCase):
    def check_scenario(self, name):
        runtime = 'const fluxPostPages={"post-a":"/","post-b":"/feed/2/"};\n' + (ROOT / 'site-assets/navigation.js').read_text()
        program = ('const runtime=' + json.dumps(runtime) + ';\n'
                   + (ROOT / 'tests/navigation_harness.js').read_text()
                   + '\nrunScenario(' + json.dumps(name) + ');')
        result = subprocess.run([ENGINE, '-e', program], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {'scenario': name, 'ok': True})

    def test_detail_measurement_replaces_old_list_click_offset(self):
        self.check_scenario('detail-offset')

    def test_direct_detail_return_keeps_page_and_frame_top(self):
        self.check_scenario('direct-detail')

    def test_native_back_restores_from_bfcache_pageshow(self):
        self.check_scenario('native-back')

    def test_image_and_font_layout_changes_keep_frame_aligned(self):
        self.check_scenario('layout-settle')

    def test_user_scrolling_stops_automatic_alignment(self):
        self.check_scenario('user-scroll')

    def test_short_final_post_gets_scroll_room_without_resizing(self):
        self.check_scenario('short-last-post')

    def test_old_pagination_bookmark_preserves_pending_frame_top(self):
        self.check_scenario('bookmark')

    def test_external_or_expired_pending_returns_are_ignored(self):
        self.check_scenario('invalid-pending')

    def test_changed_pagination_follows_pending_post(self):
        self.check_scenario('changed-page')

    def test_return_target_takes_priority_over_stale_list_hash(self):
        self.check_scenario('stale-hash')


if __name__ == '__main__':
    unittest.main()
