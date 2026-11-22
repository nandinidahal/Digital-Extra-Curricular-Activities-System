"""
End-to-end test of the DEAS frontend against the REAL backend (no mocks).
Backend: daphne on :8000 (fresh PostgreSQL DB). Frontend: vite on :5173. Browser: Chrome.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta

from PIL import Image
from playwright.sync_api import expect, sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FE = os.environ.get("E2E_FRONTEND_URL", "http://127.0.0.1:5173")
API = os.environ.get("E2E_API_URL", "http://127.0.0.1:8000/api")
MAIL = os.environ.get("E2E_MAIL_DIR", "/tmp/deas-mail")
BACKEND_DIR = os.environ.get("E2E_BACKEND_DIR", os.path.abspath(os.path.join(HERE, "../../../Backend")))
DB_NAME = os.environ.get("E2E_DB_NAME", "deas_e2e")
CHROME = os.environ.get("E2E_CHROME")  # optional path to a Chrome binary; default = Playwright's Chromium
SHOTS = os.path.join(HERE, "shots")
FILES = os.path.join(HERE, "files")
PASSWORD = "Strong!Pass#2026x"
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(FILES, exist_ok=True)
expect.set_options(timeout=15000)

results = []
console_errors = []
ALL_PAGES = []


def step(name):
    def wrap(fn):
        def run(*a, **k):
            started = time.time()
            try:
                fn(*a, **k)
                results.append((name, "PASS", f"{time.time() - started:.1f}s"))
                print(f"PASS  {name}")
            except Exception as exc:  # keep going, report at the end
                for i, open_page in enumerate(ALL_PAGES):
                    try:
                        open_page.screenshot(path=f"{SHOTS}/FAIL-{name[:30].replace(' ', '_').replace('/', '-')}-{i}.png")
                    except Exception:
                        pass
                results.append((name, "FAIL", f"{type(exc).__name__}: {str(exc)[:300]}"))
                print(f"FAIL  {name}\n      {str(exc).splitlines()[0][:300]}\n      {' | '.join(l.strip() for l in str(exc).splitlines()[1:6])[:500]}")
        return run
    return wrap


def latest_otp(email):
    deadline = time.time() + 15
    while time.time() < deadline:
        for path in sorted(glob.glob(f"{MAIL}/*.log"), key=os.path.getmtime, reverse=True):
            text = open(path, encoding="utf-8", errors="ignore").read()
            if f"To: {email}" in text:
                m = re.search(r"code is:?\s*(\d{6})", text) or re.search(r"\b(\d{6})\b", text)
                if m:
                    return m.group(1)
        time.sleep(0.5)
    raise AssertionError(f"no OTP mail for {email}")


def make_files():
    img = Image.new("RGB", (900, 500), (15, 118, 110))
    for x in range(0, 900, 60):
        for y in range(0, 500, 60):
            Image.new("RGB", (30, 30), (251, 191, 36)).save(buf := io.BytesIO(), "PNG")
            img.paste(Image.open(buf), (x, y))
    img.save(f"{FILES}/cover.jpg", "JPEG")
    Image.new("RGB", (400, 300), (200, 60, 60)).save(f"{FILES}/photo.png", "PNG")
    with open(f"{FILES}/certificate.pdf", "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n")
    with open(f"{FILES}/fake.png", "wb") as f:
        f.write(b"MZ this is not an image")


def manage(code):
    env = {**os.environ, "PYTHONPATH": HERE, "DJANGO_SETTINGS_MODULE": "e2e_settings", "DB_NAME": DB_NAME}
    out = subprocess.run([sys.executable, "manage.py", "shell", "-v", "0", "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr[-1500:])
    return out.stdout.strip()


def new_page(browser, width=1440, height=900, mobile=False):
    ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and console_errors.append(f"{m.text[:200]}"))
    page.on("pageerror", lambda e: console_errors.append(f"PAGEERROR {str(e)[:200]}"))
    page.on("response", lambda r: r.status >= 500 and console_errors.append(f"HTTP {r.status} {r.url[:120]}"))
    ALL_PAGES.append(page)
    return ctx, page


def shot(page, name, full=False):
    page.wait_for_timeout(400)
    page.screenshot(path=f"{SHOTS}/{name}.png", full_page=full)


def no_horizontal_overflow(page):
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f"horizontal overflow of {overflow}px"


def login(page, email, password=PASSWORD, next_path=None):
    page.goto(f"{FE}/login" + (f"?next={next_path}" if next_path else ""))
    page.get_by_label("Email").fill(email)
    page.get_by_label(re.compile(r"^Password\*?$")).fill(password)
    page.get_by_role("button", name="Log in").click()


def register_via_ui(page, full_name, username, email):
    page.goto(f"{FE}/register")
    page.get_by_label("Full name").fill(full_name)
    page.get_by_label("Username").fill(username)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Phone number").fill("+977 981 234 5678")
    page.get_by_label("Country").fill("Nepal")
    page.get_by_label("Date of birth").fill("2003-04-05")
    page.get_by_label(re.compile(r"^Password\*?$")).fill(PASSWORD)
    page.get_by_label("Confirm password").fill(PASSWORD)
    page.get_by_role("button", name="Create account").click()
    expect(page).to_have_url(re.compile(r"/verify-email\?email="))
    page.get_by_label("Verification code").fill(latest_otp(email))
    page.get_by_role("button", name="Verify email").click()
    expect(page).to_have_url(re.compile(r"/login\?email="))


def main():
    make_files()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx, page = new_page(browser)
        state = {}

        @step("Visitor: landing page loads with public navbar, no app navigation")
        def _():
            page.goto(FE)
            expect(page.get_by_role("heading", name=re.compile("Find your next activity"))).to_be_visible()
            expect(page.get_by_role("link", name="Log in", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Create account").first).to_be_visible()
            assert page.get_by_role("navigation", name="Main").count() == 0
            expect(page.get_by_text("No public announcements yet")).to_be_visible()
        _()

        @step("Visitor: protected route redirects to login with next")
        def _():
            page.goto(f"{FE}/home")
            expect(page).to_have_url(re.compile(r"/login\?next=%2Fhome"))
        _()

        @step("Register validation errors shown before submit")
        def _():
            page.goto(f"{FE}/register")
            page.get_by_role("button", name="Create account").click()
            expect(page.get_by_text("Enter your full name.")).to_be_visible()
            page.get_by_label("Username").fill("a b")
            page.get_by_label(re.compile(r"^Password\*?$")).fill("12345678")
            page.get_by_role("button", name="Create account").click()
            expect(page.get_by_text("Password cannot be only numbers.")).to_be_visible()
        _()

        @step("Register Alice via UI + email OTP verification")
        def _():
            register_via_ui(page, "Alice Sharma", "alice", "alice@example.com")
        _()

        @step("Server-side duplicate username error mapped onto field")
        def _():
            page.goto(f"{FE}/register")
            page.get_by_label("Full name").fill("Alice Two")
            page.get_by_label("Username").fill("alice")
            page.get_by_label("Email").fill("alice2@example.com")
            page.get_by_label("Phone number").fill("+9779812345670")
            page.get_by_label("Country").fill("Nepal")
            page.get_by_label("Date of birth").fill("2003-04-05")
            page.get_by_label(re.compile(r"^Password\*?$")).fill(PASSWORD)
            page.get_by_label("Confirm password").fill(PASSWORD)
            page.get_by_role("button", name="Create account").click()
            expect(page.get_by_text(re.compile("already exists", re.I)).first).to_be_visible()
        _()

        @step("Login: wrong password shows error; correct login lands on feed")
        def _():
            login(page, "alice@example.com", "wrong-password")
            expect(page.get_by_text("Invalid email or password.")).to_be_visible()
            login(page, "alice@example.com")
            expect(page).to_have_url(f"{FE}/home")
            expect(page.get_by_role("navigation", name="Main").first).to_be_visible()
        _()

        # Other accounts: Bob via UI (second check of the flow), Carol + coordinator via API/ORM
        def api_register(name, username, email):
            import urllib.request
            req = urllib.request.Request(f"{API}/auth/register/", data=json.dumps({
                "full_name": name, "username": username, "email": email, "password": PASSWORD, "confirm_password": PASSWORD,
                "date_of_birth": "2002-01-01", "phone_number": "+9779800000001", "country": "Nepal"}).encode(), headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req)
            req = urllib.request.Request(f"{API}/auth/verify-email/", data=json.dumps({"email": email, "otp": latest_otp(email)}).encode(), headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req)

        ctx_b, page_b = new_page(browser)

        @step("Register Bob via UI, create Carol and a coordinator")
        def _():
            register_via_ui(page_b, "Bob Thapa", "bob", "bob@example.com")
            api_register("Carol Rai", "carol", "carol@example.com")
            api_register("Dev Coordinator", "coord", "coord@example.com")
            manage("from accounts.models import User; User.objects.filter(username='coord').update(role='coordinator')")
            login(page_b, "bob@example.com")
            expect(page_b).to_have_url(f"{FE}/home")
        _()

        @step("Feed: create post with photo, visible in feed")
        def _():
            page.goto(f"{FE}/home")
            page.get_by_label("What did you do today?").fill("Our robotics team qualified for nationals! 🤖")
            page.get_by_role("button", name="Photo").click()
            with page.expect_file_chooser() as fc:
                page.get_by_role("button", name=re.compile("Add photos")).click()
            fc.value.set_files(f"{FILES}/photo.png")
            page.get_by_role("button", name="Post", exact=True).click()
            expect(page.get_by_text("Our robotics team qualified for nationals!")).to_be_visible()
            expect(page.locator("article img").first).to_be_visible()
        _()

        @step("Feed: client-side image check rejects a fake image")
        def _():
            page.get_by_role("button", name="Photo").click()
            with page.expect_file_chooser() as fc:
                page.get_by_role("button", name=re.compile("Add photos")).click()
            fc.value.set_files(f"{FILES}/fake.png")
            # The browser trusts the .png extension, so only the SERVER can detect the fake content.
            page.get_by_label("What did you do today?").fill("This upload should be refused")
            page.get_by_role("button", name="Post", exact=True).click()
            expect(page.get_by_text(re.compile("not a valid image|Unsupported|not allowed", re.I)).first).to_be_visible(timeout=8000)
            expect(page.locator("article").filter(has_text="This upload should be refused")).to_have_count(0)
            page.get_by_role("button", name="Remove fake.png").click()
            page.get_by_label("What did you do today?").fill("")
        _()

        @step("Feed: like, comment, reply, edit post")
        def _():
            post = page.locator("article").filter(has_text="Our robotics team").first
            post.get_by_role("button", name="Like").click()
            expect(post.get_by_role("button", name="Like")).to_have_attribute("aria-pressed", "true")
            post.get_by_role("button", name="Comment").first.click()
            post.get_by_label("Write a comment").fill("So proud of the team!")
            post.get_by_label("Write a comment").press("Enter")
            expect(post.get_by_text("So proud of the team!")).to_be_visible()
            post.get_by_role("button", name="Reply").first.click()
            post.get_by_label(re.compile("Reply to")).fill("Thanks everyone")
            post.get_by_label(re.compile("Reply to")).press("Enter")
            expect(post.get_by_text("Thanks everyone")).to_be_visible()
            post.get_by_role("button", name="Post actions").click()
            page.get_by_role("menuitem", name="Edit post").click()
            page.get_by_label("Text").fill("Our robotics team qualified for nationals! Final in March.")
            page.get_by_role("button", name="Save changes").click()
            expect(page.get_by_text("Final in March.")).to_be_visible()
            expect(post.get_by_text("Edited")).to_be_visible()
            page.reload()
            post = page.locator("article").filter(has_text="Final in March").first
            expect(post.get_by_role("button", name="Like")).to_have_attribute("aria-pressed", "true")
            expect(post.get_by_text("2 comments")).to_be_visible()
        _()

        @step("Announcements: create (validation), publish with cover, appears in list")
        def _():
            page.goto(f"{FE}/announcements/new")
            page.get_by_role("button", name="Publish").click()
            expect(page.get_by_text("A title is required.")).to_be_visible()
            page.get_by_label("Title").fill("Inter-college Robotics Challenge")
            page.get_by_label("Short description").fill("Build, code and race autonomous robots")
            page.get_by_label("Full description").fill("A full-day robotics challenge for teams of 3-5 students.")
            page.get_by_label("Category").select_option(label="Technology")
            page.get_by_label("Location").fill("Kathmandu Engineering College")
            start = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%dT10:00")
            page.get_by_label("Starts").fill(start)
            page.get_by_label("Ends").fill((datetime.now() + timedelta(days=10)).strftime("%Y-%m-%dT17:00"))
            page.get_by_label("Registration deadline").fill((datetime.now() + timedelta(days=11)).strftime("%Y-%m-%dT10:00"))
            page.get_by_role("button", name="Publish").click()
            expect(page.get_by_text("Registration must close on or before the start.")).to_be_visible()
            page.get_by_label("Registration deadline").fill((datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT10:00"))
            page.get_by_label("Registration link").fill("https://example.com/register")
            page.get_by_label("Email").fill("club@example.com")
            with page.expect_file_chooser() as fc:
                page.get_by_text(re.compile("Upload a cover")).click()
            fc.value.set_files(f"{FILES}/cover.jpg")
            page.get_by_role("button", name="Publish").click()
            expect(page.get_by_role("heading", name="Inter-college Robotics Challenge")).to_be_visible()
            state["announcement_url"] = page.url
            expect(page.get_by_role("link", name=re.compile("Register now"))).to_be_visible()
            expect(page.get_by_text("club@example.com")).to_be_visible()  # owner sees contact
        _()

        @step("Announcements: draft is hidden from others, search + category filter work")
        def _():
            page.goto(f"{FE}/announcements/new")
            page.get_by_label("Title").fill("Secret planning draft")
            page.get_by_role("button", name="Save draft").click()
            expect(page.get_by_text("This is a draft.")).to_be_visible()
            draft_url = page.url
            page_b.goto(draft_url)
            expect(page_b.get_by_text("Announcement not available")).to_be_visible()
            page_b.goto(f"{FE}/announcements")
            expect(page_b.get_by_text("Inter-college Robotics Challenge")).to_be_visible()
            expect(page_b.get_by_text("Secret planning draft")).to_have_count(0)
            page_b.get_by_label("Search announcements").fill("robots")
            expect(page_b.get_by_text("1 result")).to_be_visible()
            page_b.get_by_label("Search announcements").fill("zzzz-nothing")
            expect(page_b.get_by_text("No announcements match")).to_be_visible()
            page_b.get_by_role("button", name="Clear search").click()
            page_b.get_by_role("button", name="Sports").click()
            expect(page_b.get_by_text("No announcements match")).to_be_visible()
            page_b.get_by_role("button", name="Technology").click()
            expect(page_b.get_by_text("Inter-college Robotics Challenge")).to_be_visible()
            assert "category=technology" in page_b.url
        _()

        @step("Announcements: member sees no private contact; bookmark toggles")
        def _():
            page_b.goto(state["announcement_url"])
            expect(page_b.get_by_text("club@example.com")).to_have_count(0)
            expect(page_b.get_by_text(re.compile("keeps contact details private"))).to_be_visible()
            page_b.get_by_role("button", name="Bookmark", exact=True).click()
            expect(page_b.get_by_role("button", name="Bookmarked")).to_be_visible()
            page_b.goto(f"{FE}/announcements?tab=bookmarks")
            expect(page_b.get_by_text("Inter-college Robotics Challenge")).to_be_visible()
        _()

        ctx_v, visitor = new_page(browser)

        @step("Visitor: sees public card, no search/filters; clicking card -> login -> back to detail")
        def _():
            visitor.goto(FE)
            card = visitor.get_by_role("link", name="Inter-college Robotics Challenge")
            expect(card).to_be_visible()
            assert visitor.get_by_label("Search announcements").count() == 0
            card.click()
            expect(visitor).to_have_url(re.compile(r"/login\?next=%2Fannouncements%2F"))
            visitor.get_by_label("Email").fill("carol@example.com")
            visitor.get_by_label(re.compile(r"^Password\*?$")).fill(PASSWORD)
            visitor.get_by_role("button", name="Log in").click()
            expect(visitor.get_by_role("heading", name="Inter-college Robotics Challenge")).to_be_visible()
        _()
        carol = visitor

        @step("Friends: Bob sends request from Alice's profile; Alice accepts from Requests; notifications")
        def _():
            alice_id = manage("from accounts.models import User; print(User.objects.get(username='alice').pk)")
            state["alice_id"] = alice_id
            page_b.goto(f"{FE}/profile/{alice_id}")
            expect(page_b.get_by_role("heading", name="Alice Sharma")).to_be_visible()
            page_b.get_by_role("button", name="Add friend").click()
            expect(page_b.get_by_role("button", name=re.compile("Request sent"))).to_be_visible()
            page.goto(f"{FE}/notifications")
            expect(page.get_by_text("Bob Thapa sent you a friend request.")).to_be_visible()
            page.get_by_text("Bob Thapa sent you a friend request.").click()
            expect(page).to_have_url(f"{FE}/friends/requests")
            page.get_by_role("button", name="Accept").click()
            expect(page.get_by_text("No pending requests")).to_be_visible()
            page_b.reload()
            expect(page_b.get_by_text("You are friends")).to_be_visible()
        _()

        @step("Messaging: non-friend limit of 4 enforced in UI (Carol -> Alice)")
        def _():
            carol.goto(f"{FE}/profile/{state['alice_id']}")
            carol.get_by_role("button", name="Message").click()
            expect(carol).to_have_url(re.compile(r"/messages/"))
            state["carol_conv"] = carol.url
            expect(carol.get_by_text(re.compile("4 of 4 messages left"))).to_be_visible()
            box = carol.get_by_label("Message", exact=True)
            for i in range(1, 5):
                box.fill(f"Hello Alice, message {i}")
                box.press("Enter")
                expect(carol.get_by_text(f"Hello Alice, message {i}")).to_be_visible()
            expect(carol.get_by_text(re.compile("used all 4 messages"))).to_be_visible()
            expect(box).to_be_disabled()
            expect(carol.get_by_role("button", name="Send message")).to_be_disabled()
        _()

        ctx_a2, alice2 = new_page(browser)

        @step("Messaging: real-time delivery between friends over WebSocket (no reload)")
        def _():
            login(alice2, "alice@example.com")
            expect(alice2).to_have_url(f"{FE}/home")
            page_b.goto(f"{FE}/messages")
            page_b.get_by_role("button", name="New message").first.click()
            page_b.get_by_role("button", name=re.compile("Alice Sharma")).click()
            expect(page_b).to_have_url(re.compile(r"/messages/"))
            conv = page_b.url
            alice2.goto(conv)
            expect(alice2.get_by_role("heading", name="Bob Thapa").or_(alice2.get_by_text("Bob Thapa").first)).to_be_visible()
            alice2.wait_for_timeout(1500)  # socket connected
            page_b.get_by_label("Message", exact=True).fill("Hi Alice! See you at the robotics challenge?")
            page_b.get_by_label("Message", exact=True).press("Enter")
            expect(alice2.get_by_text("Hi Alice! See you at the robotics challenge?")).to_be_visible(timeout=8000)
            # friends have no limit banner
            expect(page_b.get_by_text(re.compile("messages left"))).to_have_count(0)
        _()

        @step("Notifications: live unread badge + list from real events")
        def _():
            page.goto(f"{FE}/home")
            page.wait_for_timeout(1200)
            post = page.locator("article").filter(has_text="Final in March").first
            page_b.goto(f"{FE}/home")
            bob_post = page_b.locator("article").filter(has_text="Final in March").first
            bob_post.get_by_role("button", name="Like").click()
            expect(page.get_by_role("link", name=re.compile(r"Notifications \(\d+ unread\)"))).to_be_visible(timeout=8000)
            page.goto(f"{FE}/notifications")
            expect(page.get_by_text("Bob Thapa liked your post.")).to_be_visible()
            page.get_by_role("button", name="Mark all read").click()
            expect(page.get_by_role("link", name="Notifications", exact=True)).to_be_visible()
            assert post is not None
        _()

        coord_ctx, coord = new_page(browser)

        @step("Achievements: add with PDF evidence, coordinator verifies, owner notified")
        def _():
            page.goto(f"{FE}/achievements/new")
            page.get_by_label("Title").fill("National Robotics Olympiad - Gold")
            page.get_by_label("Description").fill("Led a team of four to first place.")
            page.get_by_label("Type").select_option("competition")
            page.get_by_label("Level").select_option("national")
            page.get_by_label("Category").select_option(label="Technology")
            page.get_by_label("Organization").fill("Robotics Association of Nepal")
            page.get_by_label("Date").fill("2026-05-10")
            page.get_by_label("Position or rank").fill("1st place")
            page.get_by_label("Skills").fill("Python")
            page.get_by_label("Skills").press("Enter")
            with page.expect_file_chooser() as fc:
                page.get_by_role("button", name=re.compile("Add files")).click()
            fc.value.set_files(f"{FILES}/certificate.pdf")
            page.get_by_role("button", name="Submit for verification").click()
            expect(page.get_by_role("heading", name="National Robotics Olympiad - Gold")).to_be_visible()
            expect(page.get_by_text("Pending review").first).to_be_visible()
            expect(page.get_by_text("certificate.pdf")).to_be_visible()
            state["achievement_url"] = page.url
            login(coord, "coord@example.com")
            expect(coord).to_have_url(f"{FE}/home")
            coord.goto(f"{FE}/moderation")
            coord.get_by_role("link", name="Review").or_(coord.get_by_role("button", name="Review")).first.click()
            expect(coord.get_by_text("Review this submission")).to_be_visible()
            expect(coord.get_by_text("certificate.pdf")).to_be_visible()  # reviewer can see evidence
            coord.get_by_role("button", name="Verify").click()
            expect(coord.get_by_text("Verified").first).to_be_visible()
            page.goto(f"{FE}/notifications")
            expect(page.get_by_text(re.compile('Your achievement "National Robotics Olympiad - Gold" was verified|reviewed "National Robotics'))).to_be_visible()
        _()

        @step("Achievement privacy: Bob sees verified public one (no evidence); private -> 404")
        def _():
            url = state["achievement_url"]
            page_b.goto(url)
            expect(page_b.get_by_role("heading", name="National Robotics Olympiad - Gold")).to_be_visible()
            expect(page_b.get_by_text("certificate.pdf")).to_have_count(0)
            page.goto(url)
            page.get_by_label("Visibility").select_option("private")
            expect(page.get_by_text("Only you (and reviewers) can see it.")).to_be_visible()
            page_b.reload()
            expect(page_b.get_by_text("Achievement not available")).to_be_visible()
            page.get_by_label("Visibility").select_option("public")
            expect(page.get_by_text("Others see it once it is verified.")).to_be_visible()
        _()

        @step("Profile privacy: Alice goes private, Bob sees private notice; back to public")
        def _():
            page.goto(f"{FE}/settings/privacy")
            page.get_by_role("radio", name=re.compile("^Private")).click()
            expect(page.get_by_text("Privacy updated.").first).to_be_visible()
            page_b.goto(f"{FE}/profile/{state['alice_id']}")
            expect(page_b.get_by_text("This profile is private")).to_be_visible()
            page.get_by_role("radio", name=re.compile("^Public")).click()
            expect(page.get_by_text("Privacy updated.").first).to_be_visible()
        _()

        @step("Edit profile: headline + skills saved and shown")
        def _():
            page.goto(f"{FE}/profile/edit")
            page.get_by_label("Headline").fill("CS student · Robotics club lead")
            page.get_by_label("Skills").fill("Leadership")
            page.get_by_label("Skills").press("Enter")
            page.get_by_role("button", name="Save profile").click()
            expect(page).to_have_url(f"{FE}/profile")
            expect(page.get_by_text("CS student · Robotics club lead")).to_be_visible()
            page.get_by_role("tab", name="About").click()
            expect(page.get_by_text("Leadership")).to_be_visible()
        _()

        @step("Settings: notification preferences persist; change password keeps session")
        def _():
            page.goto(f"{FE}/settings/notifications")
            switch = page.get_by_role("switch", name="Messages")
            expect(switch).to_have_attribute("aria-checked", "true")
            switch.click()
            expect(switch).to_have_attribute("aria-checked", "false")
            page.reload()
            expect(page.get_by_role("switch", name="Messages")).to_have_attribute("aria-checked", "false")
            page.goto(f"{FE}/settings/security")
            page.get_by_label("Current password").fill(PASSWORD)
            page.get_by_label("New password", exact=True).fill(PASSWORD + "9")
            page.get_by_label("Confirm new password").fill(PASSWORD + "9")
            page.get_by_role("button", name="Update password").click()
            expect(page.get_by_text(re.compile("Password changed successfully"))).to_be_visible()
            page.goto(f"{FE}/notifications")
            expect(page.get_by_text("Password changed").first).to_be_visible()
        _()

        @step("Logout returns to landing; tokens cleared")
        def _():
            page.get_by_role("button", name="Account menu").click()
            page.get_by_role("menuitem", name="Log out").click()
            expect(page.get_by_role("heading", name=re.compile("Find your next activity"))).to_be_visible()
            stored = page.evaluate("[localStorage.getItem('deas.auth'), sessionStorage.getItem('deas.auth')]")
            assert stored == [None, None], stored
            login(page, "alice@example.com", PASSWORD + "9")
            expect(page).to_have_url(f"{FE}/home")
        _()

        @step("Forgot password: OTP -> new password -> login")
        def _():
            ctx_f, fp = new_page(browser)
            fp.goto(f"{FE}/forgot-password")
            fp.get_by_label("Email").fill("bob@example.com")
            fp.get_by_role("button", name="Send code").click()
            expect(fp.get_by_role("heading", name="Check your email")).to_be_visible()
            time.sleep(1)
            fp.get_by_label("Verification code").fill(latest_otp("bob@example.com"))
            fp.get_by_role("button", name="Verify code").click()
            fp.get_by_label("New password", exact=True).fill("Brand!New#Pass2026")
            fp.get_by_label("Confirm new password").fill("Brand!New#Pass2026")
            fp.get_by_role("button", name="Reset password").click()
            expect(fp.get_by_role("heading", name="Password updated")).to_be_visible()
            login(fp, "bob@example.com", "Brand!New#Pass2026")
            expect(fp).to_have_url(f"{FE}/home")
            ctx_f.close()
        _()

        # ------------------------------------------------------------------ screenshots + responsive
        @step("Desktop screenshots")
        def _():
            page.goto(f"{FE}/home"); expect(page.locator("article").first).to_be_visible(); shot(page, "desktop-home")
            page.goto(f"{FE}/announcements"); expect(page.get_by_text("Inter-college Robotics Challenge")).to_be_visible(); shot(page, "desktop-announcements")
            page.goto(state["announcement_url"]); expect(page.get_by_role("heading", name="Inter-college Robotics Challenge")).to_be_visible(); shot(page, "desktop-announcement-detail")
            page.goto(f"{FE}/achievements"); shot(page, "desktop-achievements")
            page.goto(state["achievement_url"]); expect(page.get_by_text("Verification history")).to_be_visible(); shot(page, "desktop-achievement-detail", full=True)
            page.goto(f"{FE}/profile"); shot(page, "desktop-profile")
            carol.goto(state["carol_conv"]); carol.wait_for_timeout(800); shot(carol, "desktop-messages-limit")
            page.goto(f"{FE}/notifications"); shot(page, "desktop-notifications")
            page.goto(f"{FE}/friends"); shot(page, "desktop-friends")
            page.goto(f"{FE}/settings/privacy"); shot(page, "desktop-settings-privacy")
            v_ctx, v = new_page(browser)
            v.goto(FE); expect(v.get_by_text("Inter-college Robotics Challenge")).to_be_visible(); shot(v, "desktop-landing", full=True)
            v.goto(f"{FE}/login"); shot(v, "desktop-login")
            v_ctx.close()
        _()

        @step("Mobile (390px): no horizontal overflow on main pages + screenshots")
        def _():
            m_ctx, m = new_page(browser, 390, 844, mobile=True)
            m.goto(FE); expect(m.get_by_text("Inter-college Robotics Challenge")).to_be_visible(); no_horizontal_overflow(m); shot(m, "mobile-landing")
            login(m, "alice@example.com", PASSWORD + "9")
            expect(m).to_have_url(f"{FE}/home")
            for path, name in [("/home", "home"), ("/announcements", "announcements"), (state["announcement_url"].replace(FE, ""), "announcement-detail"),
                               ("/achievements", "achievements"), ("/profile", "profile"), ("/friends", "friends"), ("/messages", "messages"),
                               ("/notifications", "notifications"), ("/settings", "settings")]:
                m.goto(FE + path)
                m.wait_for_load_state("networkidle")
                no_horizontal_overflow(m)
                shot(m, f"mobile-{name}")
            expect(m.get_by_role("navigation", name="Main").last).to_be_visible()  # bottom tab bar
            m.goto(f"{FE}/messages")
            m.get_by_role("button", name=re.compile("Bob Thapa")).click()
            expect(m.get_by_label("Back to conversations")).to_be_visible()
            no_horizontal_overflow(m)
            shot(m, "mobile-conversation")
            m_ctx.close()
        _()

        @step("Tablet (820px): no horizontal overflow")
        def _():
            t_ctx, t = new_page(browser, 820, 1180)
            login(t, "bob@example.com", "Brand!New#Pass2026")
            for path in ["/home", "/announcements", "/messages", "/achievements", "/profile"]:
                t.goto(FE + path); t.wait_for_load_state("networkidle"); no_horizontal_overflow(t)
            shot(t, "tablet-home")
            t_ctx.close()
        _()

        browser.close()

    print("\n================ RESULTS ================")
    for name, status, detail in results:
        print(f"{status:4}  {name}  ({detail})")
    passed = sum(1 for r in results if r[1] == "PASS")
    print(f"\n{passed}/{len(results)} steps passed")
    relevant = [e for e in console_errors if "ERR_TUNNEL_CONNECTION_FAILED" not in e]
    print(f"Browser console errors: {len(relevant)}")
    for e in relevant[:30]:
        print("  ", e)


if __name__ == "__main__":
    main()
