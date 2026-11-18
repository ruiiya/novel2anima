"""Quà Kỷ Niệm — BLIND story materialization + 122-shot storyboard draft.

Creates the Story, roles, plan, acts, beats and events in the local DB.
Writes a storyboard draft for review but does NOT save it (separate approval gate).
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "database/src")
from n2m_db import add_role, connect, create_story, sha  # noqa: E402
from n2m_workflow import add_act, add_beat, add_event, save_plan  # noqa: E402

DB = pathlib.Path("database/data/novel2anima.db")
ROOT = pathlib.Path("exports/anniversary_gift")
ROOT.mkdir(parents=True, exist_ok=True)
STATE = ROOT / "state.json"

TITLE = "Quà Kỷ Niệm"
LABELS = ["nsfw", "explicit", "adult", "consensual", "hotwife", "qos", "interracial", "no_tattoo", "blind_cast"]
POLICY = {"policy_id": "N2M-CONTENT-POLICY", "policy_version": "1.3.0"}
APPROVED_AT = "2026-11-17T00:00:00Z"


def B(summary, safety, shots, location, props, roles, transition,
      moments, purposes, cameras, actor, target, action, reaction, state,
      pose, expression, outfit):
    return {
        "summary": summary, "safety": safety, "shots": shots,
        "location": location, "props": props, "roles": roles, "transition": transition,
        "moments": moments, "purposes": purposes, "cameras": cameras,
        "event": {
            "actor": actor, "target": target, "action": action, "reaction": reaction,
            "state": state,
            "spec": {"pose": pose, "expression": expression, "outfit": outfit, "safety": safety},
        },
    }


ACTS = [
    {
        "title": "Nhận phòng",
        "summary": "Cô đến suite một mình, chuẩn bị như một nghi thức, chờ người tình.",
        "spec": {"part": "P1", "time": "Friday 20:00-22:00", "zones": ["living", "bedroom", "door"],
                 "arc": "arrival -> ritual -> wait -> lover arrives", "shot_budget": 25},
        "beats": [
            B("Cô mở cửa suite một mình; key card, đèn ấm, city lights.", "sensitive", 3,
              "LOC_SUITE_LIVING", ["PROP_LUGGAGE"], ["WIFE_A"], "TIME_CUT",
              ["wide suite interior with city lights",
               "she stops in the doorway with her key card",
               "key card and weekend bag on the console"],
              ["ESTABLISHING", "ACTION", "DETAIL"],
              ["wide shot, eye level", "full body, from side", "close-up, from side"],
              "WIFE_A", None, "enters the suite alone and stops in the doorway",
              "she exhales and looks at the city", "arrival; travel clothes; luggage in hand",
              "standing in the doorway", "quiet awe", "travel clothes, coat, weekend bag"),
            B("Thiệp trên gối; cô đọc, xoay nhẫn, nhắn chồng.", "sensitive", 3,
              "LOC_SUITE_BED", ["PROP_NOTE", "PROP_RING", "PROP_PHONE"], ["WIFE_A"], "TIME_CUT",
              ["handwritten note on the pillow",
               "she turns the wedding ring on her finger",
               "phone screen with 'I'm here' and his reply"],
              ["DETAIL", "ACTION", "REACTION"],
              ["close-up, from side", "close-up, eye level", "close-up, eye level"],
              "WIFE_A", None, "reads the handwritten note and texts her husband",
              "she smiles and touches her ring", "note read; text sent; ring turned",
              "sitting on the bed", "soft smile", "black dress still in the box, robe"),
            B("Cô mở hộp, trải váy đen; bỏ đồ travel.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_DRESS", "PROP_LUGGAGE"], ["WIFE_A"], "CAMERA_CUT",
              ["she lifts the black dress from the box",
               "the travel clothes fall over a chair"],
              ["ACTION", "DETAIL"],
              ["cowboy shot, from side", "close-up, from side"],
              "WIFE_A", None, "unpacks the black dress and lays it on the bed",
              "she steps out of her travel clothes", "travel clothes off; robe on; dress on bed",
              "standing at the bed", "focused", "robe; black dress on the bed"),
            B("Rót champagne, đặt pendant trên vanity.", "sensitive", 2,
              "LOC_SUITE_LIVING", ["PROP_CHAMPAGNE", "PROP_PENDANT"], ["WIFE_A"], "LOCATION_CUT",
              ["champagne poured into two glasses",
               "the spade pendant placed on the vanity"],
              ["ACTION", "DETAIL"],
              ["close-up, from side", "close-up, eye level"],
              "WIFE_A", None, "pours champagne and sets the pendant on the vanity",
              "she looks at the pendant", "champagne poured; pendant on vanity",
              "standing at the vanity", "quiet", "robe; pendant in hand"),
            B("Mặc váy, kéo khóa, heels, slit.", "sensitive", 3,
              "LOC_SUITE_BED", ["PROP_DRESS", "PROP_PENDANT", "PROP_RING"], ["WIFE_A"], "LOCATION_CUT",
              ["the zipper closes up her back",
               "heels and the dress slit over one leg",
               "she stands by the window in the black dress"],
              ["ACTION", "DETAIL", "ESTABLISHING"],
              ["close-up, from side", "close-up, from side", "full body, from side"],
              "WIFE_A", None, "zips herself into the black dress and puts on heels",
              "she checks the slit and her reflection", "black dress on; heels; pendant; ring",
              "standing by the window", "composed", "black evening dress, heels, pendant, ring"),
            B("Chờ: ngồi mép giường, check phone, window, suýt cancel.", "sensitive", 3,
              "LOC_SUITE_BED", ["PROP_PHONE"], ["WIFE_A"], "CAMERA_CUT",
              ["she sits on the edge of the bed with the phone",
               "city lights beyond the window",
               "her thumb hovers over the cancel message"],
              ["ACTION", "ESTABLISHING", "DETAIL"],
              ["full body, from side", "wide shot, eye level", "close-up, from side"],
              "WIFE_A", None, "waits on the edge of the bed and almost cancels",
              "she puts the phone face-down and breathes", "anxious; phone face-down",
              "sitting on the bed", "nervous", "black evening dress, heels"),
            B("Knock; cô khựng, bước tới, tay trên tay nắm, mở.", "sensitive", 4,
              "LOC_SUITE_DOOR", [], ["WIFE_A"], "LOCATION_CUT",
              ["the suite door from inside",
               "she freezes at the knock",
               "her hand on the brass handle",
               "the door opens"],
              ["ESTABLISHING", "REACTION", "DETAIL", "ACTION"],
              ["wide shot, eye level", "upper body, three-quarter view", "close-up, from side", "full body, eye level"],
              "PARTNER_B", "WIFE_A", "knocks on the suite door",
              "she freezes, then opens the door", "door open",
              "standing at the door", "held breath", "black evening dress, heels"),
            B("Anh vào, áo mưa, hộp dessert; kiss; zip.", "nsfw", 5,
              "LOC_SUITE_DOOR", ["PROP_DESSERT", "PROP_DRESS"], ["WIFE_A", "PARTNER_B"], "CONTINUOUS",
              ["the open doorway with him in the corridor light",
               "rain on his coat and the dessert box in his hand",
               "their first look",
               "the first kiss",
               "his hand on the zipper at her back"],
              ["ESTABLISHING", "DETAIL", "REACTION", "CLIMAX", "DETAIL"],
              ["wide shot, eye level", "close-up, from side", "upper body, three-quarter view",
               "close-up, eye level", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "steps in, sets down the dessert box, and kisses her",
              "she pulls him closer and lets him unzip the dress", "dress unzipped to waist",
              "standing in the doorway", "hungry", "rain-damp coat, dark shirt; black dress"),
        ],
    },
    {
        "title": "Đêm đầu",
        "summary": "Bữa tối, foreplay, hiệp một, nghỉ, hiệp hai.",
        "spec": {"part": "P2", "time": "Friday 22:00-02:00",
                 "zones": ["dining", "living", "bed", "window"],
                 "arc": "dinner -> foreplay -> first sex -> interlude -> second sex", "shot_budget": 28},
        "beats": [
            B("Dinner: champagne, dessert, feeding.", "nsfw", 2,
              "LOC_SUITE_DINING", ["PROP_CHAMPAGNE", "PROP_DESSERT", "PROP_DRESS"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the dining table with champagne and dessert",
               "she lifts a spoon to his lips"],
              ["ESTABLISHING", "ACTION"],
              ["wide shot, eye level", "cowboy shot, from side"],
              "WIFE_A", "PARTNER_B", "feeds him dessert at the table",
              "he laughs and holds her wrist", "dinner; dress open",
              "sitting at the table", "playful", "black dress unzipped, dessert, champagne"),
            B("Tay anh dưới bàn, lên đùi, qua slit; cô giữ mặt.", "nsfw", 3,
              "LOC_SUITE_DINING", ["PROP_DRESS"], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["her composed face over the table",
               "his hand under the table on her knee",
               "his fingers at the dress slit"],
              ["REACTION", "ACTION", "DETAIL"],
              ["upper body, eye level", "close-up, from side", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "slides his hand under the table and up her thigh",
              "she keeps her face composed and grips her glass", "dress slit open; thighs bare",
              "sitting at the table", "composed, flushed", "black dress slit open"),
            B("Cô đẩy anh vào armchair, straddle, ready.", "nsfw", 4,
              "LOC_SUITE_LIVING", ["PROP_DRESS", "PROP_PENDANT"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["she pushes him into the armchair",
               "she straddles him",
               "the dress bunched at her waist",
               "their faces close; 'ready?' 'yes'"],
              ["ESTABLISHING", "ACTION", "DETAIL", "REACTION"],
              ["wide shot, eye level", "cowboy shot, from side", "close-up, from side", "close-up, eye level"],
              "WIFE_A", "PARTNER_B", "pushes him into the armchair and straddles him",
              "he grips the chair arms and nods", "dress around waist; lingerie visible",
              "straddling him in the armchair", "bold", "black dress around waist, black lingerie, pendant"),
            B("Oral: quỳ, tay anh trong tóc, pendant.", "explicit", 4,
              "LOC_SUITE_LIVING", ["PROP_PENDANT"], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["the armchair from the side",
               "she kneels between his legs",
               "his hand in her hair",
               "the pendant swinging"],
              ["ESTABLISHING", "ACTION", "REACTION", "DETAIL"],
              ["wide shot, eye level", "cowboy shot, from side", "upper body, three-quarter view", "close-up, from side"],
              "WIFE_A", "PARTNER_B", "takes him in her mouth",
              "his head falls back and his hand tightens in her hair", "oral; saliva",
              "kneeling between his legs", "focused", "black lingerie, pendant, heels"),
            B("First penetration: cowgirl trên ghế.", "explicit", 4,
              "LOC_SUITE_LIVING", ["PROP_PENDANT"], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["she climbs back onto his lap",
               "she guides him inside her",
               "cowgirl on the armchair",
               "her hands on his shoulders"],
              ["ACTION", "ACTION", "CLIMAX", "DETAIL"],
              ["cowboy shot, from side", "close-up, from side", "cowboy shot, from side", "close-up, from side"],
              "WIFE_A", "PARTNER_B", "guides him inside her and rides him on the armchair",
              "he thrusts up and holds her hips", "first penetration; cowgirl",
              "cowgirl on the armchair", "half-closed eyes", "black lingerie pulled aside, pendant"),
            B("Bed: missionary, cowgirl, cười.", "explicit", 3,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["they move to the bed",
               "missionary with her leg over his shoulder",
               "cowgirl; she laughs"],
              ["ESTABLISHING", "ACTION", "REACTION"],
              ["wide shot, eye level", "full body, from side", "cowboy shot, from side"],
              "PARTNER_B", "WIFE_A", "moves her to the bed and takes her in missionary",
              "she laughs and pulls him down", "bed; lingerie off",
              "on the bed", "laughing, flushed", "nude, pendant"),
            B("From behind ở mép giường; cô nhìn lại.", "explicit", 3,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["her hands on the mattress",
               "he takes her from behind",
               "she looks back over her shoulder"],
              ["DETAIL", "ACTION", "REACTION"],
              ["close-up, from side", "full body, from side", "upper body, three-quarter view"],
              "PARTNER_B", "WIFE_A", "takes her from behind at the edge of the bed",
              "she looks back and he kisses her shoulder", "from behind",
              "on all fours at the bed edge", "breathless", "nude, pendant, black silk"),
            B("Climax đầu: cum on body; collapse.", "explicit", 5,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["wide bed with both bodies",
               "her back arches",
               "his hand on her hip",
               "cum on her stomach",
               "they collapse on the black silk"],
              ["ESTABLISHING", "CLIMAX", "ACTION", "DETAIL", "AFTERMATH"],
              ["wide shot, eye level", "cowboy shot, from side", "close-up, from side",
               "close-up, from side", "wide shot, eye level"],
              "PARTNER_B", "WIFE_A", "finishes on her stomach",
              "she arches and trembles", "afterglow; sweat",
              "lying on the bed", "spent", "nude, cum on stomach, black silk"),
        ],
    },
    {
        "title": "Sáng thứ bảy",
        "summary": "Thức giấc, breakfast, bath, terrace, nap.",
        "spec": {"part": "P3", "time": "Saturday 08:00-14:00", "zones": ["bed", "terrace", "bath"],
                 "arc": "wake -> breakfast -> bath -> terrace -> noon nap", "shot_budget": 20},
        "beats": [
            B("Morning; shirt; pendant nightstand.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_PENDANT"], ["WIFE_A"], "TIME_CUT",
              ["morning light on the black silk",
               "she sits up in his white shirt, pendant on the nightstand"],
              ["ESTABLISHING", "DETAIL"],
              ["wide shot, eye level", "upper body, from side"],
              "WIFE_A", None, "wakes in his shirt",
              "she touches the pendant on the nightstand", "morning; shirt only",
              "sitting up in bed", "soft, sleepy", "white shirt, pendant on nightstand"),
            B("Breakfast trên terrace.", "sensitive", 2,
              "LOC_SUITE_TERRACE", ["PROP_BREAKFAST"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["room service tray on the terrace",
               "coffee and croissant; city day"],
              ["ESTABLISHING", "DETAIL"],
              ["wide shot, eye level", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "pours coffee on the terrace",
              "she wraps the robe and sits", "breakfast; robe",
              "sitting at the terrace table", "relaxed", "white robe, coffee, croissant"),
            B("Bath: wash each other, kiss.", "nsfw", 3,
              "LOC_SUITE_BATH", ["PROP_TOWEL"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the deep tub filled with water",
               "she washes his shoulders",
               "a kiss in the water"],
              ["ESTABLISHING", "ACTION", "REACTION"],
              ["wide shot, eye level", "cowboy shot, from side", "close-up, eye level"],
              "WIFE_A", "PARTNER_B", "washes his shoulders in the bath",
              "he pulls her into a kiss", "wet skin; nude",
              "in the bath", "tender", "nude, wet skin, towel nearby"),
            B("Terrace kiss; hand inside robe.", "nsfw", 3,
              "LOC_SUITE_TERRACE", ["PROP_TOWEL"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the terrace railing and skyline",
               "she leans on the railing in the robe",
               "his hand slips inside the robe"],
              ["ESTABLISHING", "ACTION", "DETAIL"],
              ["wide shot, eye level", "full body, from side", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "kisses her at the railing and slips a hand inside her robe",
              "she leans back into him", "robe open; daylight",
              "leaning on the railing", "warm", "white robe open, daylight"),
            B("Noon lazy sex; spooning; nap.", "explicit", 3,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the bed in daylight",
               "lazy missionary",
               "spooning; her eyes close"],
              ["ESTABLISHING", "ACTION", "AFTERMATH"],
              ["wide shot, eye level", "full body, from side", "cowboy shot, from side"],
              "PARTNER_B", "WIFE_A", "takes her slowly in the afternoon light",
              "she sighs and holds his arm", "lazy sex; nap",
              "on the bed", "drowsy", "nude, daylight, white sheet"),
            B("Talk: arrangement, ring, phone photo.", "sensitive", 3,
              "LOC_SUITE_BED", ["PROP_RING", "PROP_PHONE", "PROP_PENDANT"], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["they sit against the headboard",
               "he turns the wedding ring on her finger",
               "she sends the pendant photo to her husband"],
              ["ESTABLISHING", "DETAIL", "ACTION"],
              ["cowboy shot, from side", "close-up, from side", "close-up, eye level"],
              "WIFE_A", "PARTNER_B", "talks about the arrangement and sends a photo to her husband",
              "he traces her wedding ring", "emotional intimacy",
              "sitting against the headboard", "open", "white sheet, ring, phone, pendant"),
            B("Second gift: lingerie.", "nsfw", 2,
              "LOC_SUITE_BED", ["PROP_LINGERIE"], ["WIFE_A"], "TIME_CUT",
              ["a new box on the bed",
               "black lingerie held against her body"],
              ["DETAIL", "ACTION"],
              ["close-up, from side", "cowboy shot, eye level"],
              "WIFE_A", None, "opens the second gift and holds the lingerie against herself",
              "she smiles at the note", "new lingerie",
              "standing by the bed", "amused", "white sheet, black lingerie"),
            B("Slow dance; kiss; fade.", "sensitive", 2,
              "LOC_SUITE_LIVING", ["PROP_RED_DRESS"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the living room in late afternoon",
               "they dance slowly; kiss"],
              ["ESTABLISHING", "ACTION"],
              ["wide shot, eye level", "cowboy shot, from side"],
              "PARTNER_B", "WIFE_A", "dances with her in the living room",
              "she rests her head on his shoulder", "late afternoon; dressed for night two",
              "dancing", "soft", "red dress, pendant"),
        ],
    },
    {
        "title": "Đêm thứ hai",
        "summary": "Dressing, dinner, husband call, roleplay, climax.",
        "spec": {"part": "P4", "time": "Saturday 19:00-02:00", "zones": ["bedroom", "dining", "living"],
                 "arc": "dressing -> dinner -> call -> roleplay -> climax", "shot_budget": 28},
        "beats": [
            B("Dressing: red dress, pendant.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_RED_DRESS", "PROP_PENDANT"], ["WIFE_A"], "TIME_CUT",
              ["the red dress laid on the bed",
               "she fastens the pendant"],
              ["DETAIL", "ACTION"],
              ["close-up, from side", "close-up, from side"],
              "WIFE_A", None, "dresses in the red dress and fastens the pendant",
              "she checks herself in the mirror", "red dress; pendant",
              "standing at the bed", "composed", "red dress, pendant, heels"),
            B("Dinner: candle, wine.", "nsfw", 2,
              "LOC_SUITE_DINING", ["PROP_WINE"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["candlelit table",
               "she lifts a glass of wine"],
              ["ESTABLISHING", "ACTION"],
              ["wide shot, eye level", "cowboy shot, from side"],
              "WIFE_A", "PARTNER_B", "toasts him at the candlelit table",
              "he touches her glass", "dinner; wine",
              "sitting at the table", "warm", "red dress, wine, candlelight"),
            B("Phone rings; husband's voice.", "nsfw", 4,
              "LOC_SUITE_LIVING", ["PROP_PHONE"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the room phone on the side table",
               "her hand on the receiver",
               "she looks at the lover",
               "the lover behind her"],
              ["DETAIL", "ACTION", "REACTION", "ESTABLISHING"],
              ["close-up, from side", "close-up, from side", "upper body, three-quarter view", "cowboy shot, from side"],
              "HUSBAND_C", "WIFE_A", "calls the suite phone",
              "she answers and looks at the lover", "phone at her ear; lover behind",
              "standing by the side table", "startled, then steady", "red dress, phone"),
            B("Call; neck kiss; steady voice.", "nsfw", 5,
              "LOC_SUITE_LIVING", ["PROP_PHONE", "PROP_RED_DRESS"], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["her face with the phone",
               "his lips on her neck",
               "her hand gripping the phone",
               "her eyes half closed",
               "the red dress strap slipping"],
              ["REACTION", "ACTION", "DETAIL", "REACTION", "DETAIL"],
              ["close-up, eye level", "close-up, from side", "close-up, from side",
               "close-up, eye level", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "kisses her neck while she is on the phone",
              "she keeps her voice steady and grips the phone", "dress strap down; tension",
              "standing, phone at ear", "strained pleasure", "red dress strap down, phone"),
            B("Permission: 'take your time'.", "sensitive", 3,
              "LOC_SUITE_LIVING", ["PROP_PHONE", "PROP_RING"], ["WIFE_A"], "CAMERA_CUT",
              ["her face as she listens",
               "the phone screen ending the call",
               "she exhales"],
              ["REACTION", "DETAIL", "AFTERMATH"],
              ["close-up, eye level", "close-up, from side", "upper body, eye level"],
              "HUSBAND_C", "WIFE_A", "tells her to take her time",
              "she thanks him and exhales", "permission reaffirmed",
              "standing by the side table", "grateful, relieved", "red dress, phone, ring"),
            B("Roleplay: kể lại, bế lên bàn, sex chậm.", "explicit", 4,
              "LOC_SUITE_DINING", ["PROP_RED_DRESS"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["she tells him what the husband said",
               "he lifts her onto the dining table",
               "the red dress around her waist",
               "slow face-to-face sex"],
              ["ACTION", "ESTABLISHING", "DETAIL", "CLIMAX"],
              ["upper body, from side", "wide shot, eye level", "close-up, from side", "cowboy shot, from side"],
              "PARTNER_B", "WIFE_A", "lifts her onto the table and takes her slowly",
              "she holds his face", "red dress around waist",
              "sitting on the dining table", "intense", "red dress around waist, nude below"),
            B("Bed: missionary, cowgirl, from behind.", "explicit", 3,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["missionary on the bed",
               "cowgirl; she leans down",
               "from behind; he holds her hair"],
              ["ACTION", "ACTION", "REACTION"],
              ["full body, from side", "cowboy shot, from side", "upper body, three-quarter view"],
              "PARTNER_B", "WIFE_A", "takes her through three positions on the bed",
              "she calls his name", "intense; sweat",
              "on the bed", "overwhelmed", "nude, pendant, black silk"),
            B("Climax hai; afterglow.", "explicit", 5,
              "LOC_SUITE_BED", [], ["WIFE_A", "PARTNER_B"], "CAMERA_CUT",
              ["wide bed",
               "her back arches",
               "his hand on her waist",
               "cum on her body",
               "he holds her; afterglow"],
              ["ESTABLISHING", "CLIMAX", "ACTION", "DETAIL", "AFTERMATH"],
              ["wide shot, eye level", "cowboy shot, from side", "close-up, from side",
               "close-up, from side", "wide shot, eye level"],
              "PARTNER_B", "WIFE_A", "finishes on her body",
              "she trembles and he holds her", "spent; held",
              "lying on the bed", "spent, safe", "nude, cum on body, black silk"),
        ],
    },
    {
        "title": "Chủ nhật",
        "summary": "Morning, packing, bath, rời đi, cửa khép.",
        "spec": {"part": "P5", "time": "Sunday 08:00-11:00", "zones": ["bed", "bath", "door"],
                 "arc": "morning -> packing -> bath -> departure -> adjoining door", "shot_budget": 21},
        "beats": [
            B("Morning; rain stopped; pendant.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_PENDANT"], ["WIFE_A"], "TIME_CUT",
              ["pale morning light; rain stopped",
               "pendant on the pillow"],
              ["ESTABLISHING", "DETAIL"],
              ["wide shot, eye level", "close-up, from side"],
              "WIFE_A", None, "wakes in the last morning light",
              "she looks at the pendant", "last morning; shirt only",
              "sitting up in bed", "quiet", "white shirt, pendant on pillow"),
            B("Packing; pendant on bed.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_DRESS", "PROP_PENDANT", "PROP_LUGGAGE"], ["WIFE_A"], "CAMERA_CUT",
              ["she folds the black dress",
               "the pendant left on the bed"],
              ["ACTION", "DETAIL"],
              ["cowboy shot, from side", "close-up, from side"],
              "WIFE_A", None, "packs the dresses and leaves the pendant on the bed",
              "she pauses over it", "packing; pendant on bed",
              "standing at the bed", "pensive", "travel clothes, pendant on bed"),
            B("Last shower; tender.", "nsfw", 2,
              "LOC_SUITE_BATH", ["PROP_TOWEL"], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the shower running",
               "their hands under the water"],
              ["ESTABLISHING", "DETAIL"],
              ["wide shot, eye level", "close-up, from side"],
              "PARTNER_B", "WIFE_A", "washes her back in the shower",
              "she leans into him", "clean; tender",
              "standing under the shower", "soft", "nude, wet skin, towel"),
            B("Dressing; tray; tip.", "sensitive", 2,
              "LOC_SUITE_BED", ["PROP_TRAY", "PROP_LUGGAGE"], ["WIFE_A"], "LOCATION_CUT",
              ["travel clothes on the bed",
               "room service tray with a tip"],
              ["ACTION", "DETAIL"],
              ["cowboy shot, from side", "close-up, from side"],
              "WIFE_A", None, "dresses in travel clothes and leaves a tip",
              "she takes one last look at the suite", "ready to leave",
              "standing by the bed", "composed", "travel clothes, luggage, tray"),
            B("Lover leaves; last kiss.", "sensitive", 3,
              "LOC_SUITE_DOOR", [], ["WIFE_A", "PARTNER_B"], "LOCATION_CUT",
              ["the suite door",
               "the last kiss",
               "she watches him go"],
              ["ESTABLISHING", "ACTION", "REACTION"],
              ["wide shot, eye level", "close-up, eye level", "upper body, three-quarter view"],
              "PARTNER_B", "WIFE_A", "kisses her one last time at the suite door",
              "she watches him leave", "alone in suite",
              "standing at the door", "wistful", "travel clothes"),
            B("Adjoining door: hand on handle, ring.", "sensitive", 4,
              "LOC_SUITE_DOOR", ["PROP_RING"], ["WIFE_A"], "CAMERA_CUT",
              ["the adjoining door",
               "her hand on the handle",
               "the wedding ring",
               "her face"],
              ["ESTABLISHING", "ACTION", "DETAIL", "REACTION"],
              ["wide shot, eye level", "close-up, from side", "close-up, from side", "upper body, eye level"],
              "WIFE_A", None, "stands before the adjoining door with her hand on the handle",
              "she steadies herself", "decision",
              "standing before the door", "resolved", "travel clothes, ring"),
            B("Door opens off-frame; she steps through.", "sensitive", 3,
              "LOC_SUITE_DOOR", ["PROP_RING"], ["WIFE_A"], "CAMERA_CUT",
              ["the door opening from the other side",
               "her foot crossing the threshold",
               "the empty threshold"],
              ["ACTION", "DETAIL", "AFTERMATH"],
              ["wide shot, eye level", "close-up, from side", "wide shot, eye level"],
              "HUSBAND_C", "WIFE_A", "opens the adjoining door from the other side",
              "she steps through", "she crosses",
              "crossing the threshold", "quiet", "travel clothes, ring"),
            B("Empty suite; pendant on pillow; final.", "sensitive", 3,
              "LOC_SUITE_BED", ["PROP_PENDANT"], [], "TIME_CUT",
              ["the empty bed",
               "the pendant on the pillow",
               "the city morning through the window"],
              ["ESTABLISHING", "DETAIL", "AFTERMATH"],
              ["wide shot, eye level", "close-up, from side", "wide shot, eye level"],
              None, None, "the suite settles into morning",
              "the pendant remains on the pillow", "end",
              "empty room", "still", "empty suite, pendant on pillow"),
        ],
    },
]


def source_brief() -> str:
    lines = [
        "# Quà Kỷ Niệm — Story Brief (approved)",
        "",
        "**Cast mode:** BLIND",
        "**Approval:** user approved the 122-shot brief on 2026-11-17.",
        "**Policy:** N2M-CONTENT-POLICY@1.3.0",
        "",
        "## Premise",
        "",
        "Đêm kỷ niệm 5 năm cưới. Người chồng đặt một suite khách sạn, để trên giường một chiếc váy đen, "
        "một mặt dây chuyền hình bích nhỏ và một tấm thiệp. Anh sang phòng bên cạnh, khép cửa. Người vợ "
        "mặc váy, đeo pendant, nhắn `green` cho chồng, rồi mở cửa cho người tình da đen quen thuộc. "
        "Story kéo dài một cuối tuần trong cùng suite; người chồng không bao giờ vào khung.",
        "",
        "## Roles (blind)",
        "",
        "| Role | Ràng buộc | Placeholder |",
        "|---|---|---|",
        "| `WIFE_A` | adult married woman; bind phải `CONFIRMED_ADULT/REVIEWED`; **no tattoo** | elegant adult woman, medium-full build, wedding ring; face/hair do casting quyết định |",
        "| `PARTNER_B` | adult Black man; bind phải `CONFIRMED_ADULT/REVIEWED`; **no tattoo** | tall, athletic, dark skin, short black hair, trimmed beard; chef |",
        "| `HUSBAND_C` | adult man; **off-frame only** | voice qua cửa, phone text, nhẫn cưới, adjoining door; không vào shot nào |",
        "",
        "## Timeline — 5 Part",
        "",
        "| Part | Thời gian | Zone | Arc | Shot |",
        "|---|---|---|---|---|",
    ]
    for act in ACTS:
        s = act["spec"]
        lines.append(f"| {s['part']} — {act['title']} | {s['time']} | {', '.join(s['zones'])} | {s['arc']} | {s['shot_budget']} |")
    lines += ["", "## 40 Beat", ""]
    for act in ACTS:
        lines.append(f"### {act['spec']['part']} — {act['title']}")
        for i, beat in enumerate(act["beats"], 1):
            lines.append(f"- **{act['spec']['part']}.B{i:02d}** — {beat['summary']} ({beat['safety']}, {beat['shots']})")
        lines.append("")
    total = sum(b["shots"] for a in ACTS for b in a["beats"])
    lines += [
        "## Shot budget",
        "",
        f"**{total} shot** = " + " + ".join(str(a['spec']['shot_budget']) for a in ACTS) + ".",
        "Mỗi beat có 2–5 shot theo nhu cầu: `1 base + 1 geography + 1 state/prop + 1 reaction + 1 climax`, cap 5.",
        "Không ép 5 shot/beat. Không thêm shot nếu không mang thông tin mới.",
        "",
        "## Constraints",
        "",
        "- `1boy, 1girl, hetero` trong mọi shot sex; không `solo`.",
        "- `HUSBAND_C` off-frame tuyệt đối: voice, phone text, ring, adjoining door.",
        "- **Không tattoo** — pendant là prop, không phải body art.",
        "- Consensual: `green` ở P1.B02; `Ready?` ở P2.B03; `Take your time` ở P4.B05.",
        "- Một location: suite + 5 zone; không corridor/balcony công cộng.",
        "- `WIFE_A` và `PARTNER_B` phải bind `CONFIRMED_ADULT/REVIEWED` trước `PROMPT_DERIVATION`.",
        "",
    ]
    return "\n".join(lines)


def find_or_create_story(con):
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
        sid = state.get("story_id")
        if sid and con.execute("SELECT 1 FROM stories WHERE id=?", (sid,)).fetchone():
            return sid, state
    row = con.execute("SELECT id FROM stories WHERE title=? AND cast_mode='BLIND' ORDER BY rowid DESC LIMIT 1",
                      (TITLE,)).fetchone()
    if row:
        return row["id"], None
    brief = (ROOT / "source_brief.md").read_text(encoding="utf-8")
    sid = create_story(con, TITLE, "BLIND", brief, LABELS)
    return sid, None


def main():
    con = connect(DB)
    story_id, state = find_or_create_story(con)
    print("story:", story_id)

    role_ids = {}
    role_specs = [
        ("WIFE_A", "adult married woman; appearance TBD at bind; no tattoo; wedding ring; must bind CONFIRMED_ADULT/REVIEWED"),
        ("PARTNER_B", "adult Black man; tall athletic; short black hair; trimmed beard; no tattoo; chef; must bind CONFIRMED_ADULT/REVIEWED"),
        ("HUSBAND_C", "adult man; off-frame only: voice, phone text, wedding ring, adjoining door"),
    ]
    for key, desc in role_specs:
        role_ids[key] = add_role(con, story_id, key, desc)
    print("roles:", role_ids)

    brief = (ROOT / "source_brief.md").read_text(encoding="utf-8")
    acts_plan = []
    for ai, act in enumerate(ACTS, 1):
        beats = []
        for bi, beat in enumerate(act["beats"], 1):
            ev = beat["event"]
            beats.append({
                "beat_id": f"{act['spec']['part']}.B{bi:02d}",
                "type": beat["purposes"][0].lower(),
                "summary": beat["summary"],
                "events": [{
                    "event_id": f"{act['spec']['part']}.E{bi:02d}",
                    "actor_id": ev["actor"], "target_id": ev["target"],
                    "primary_action": ev["action"], "reaction": ev["reaction"],
                    "state_change": ev["state"],
                    "spec": {**ev["spec"], "shot_budget": beat["shots"],
                             "moments": beat["moments"], "purposes": beat["purposes"],
                             "cameras": beat["cameras"], "location_key": beat["location"],
                             "prop_keys": beat["props"], "role_keys": beat["roles"]},
                }],
            })
        acts_plan.append({"act_id": f"A{ai:02d}", "title": act["title"], "summary": act["summary"],
                          "spec": act["spec"], "beats": beats})

    plan = {
        "schema_version": "n2m.story_plan.v1",
        "story_id": story_id,
        "title": TITLE,
        "cast_mode": "BLIND",
        "source_refs": [{"type": "user_input", "path": str(ROOT / "source_brief.md"), "sha256": sha(brief)}],
        "approval": {"status": "APPROVED", "approved_by": "user", "approved_at": APPROVED_AT,
                     "evidence": "User said ok to the 122-shot brief (5 parts x 8 beats, 122 shots).",
                     **POLICY},
        "intent": {
            "content_profile": "erotic_weekend_album",
            "raw_labels": LABELS,
            "constraints": [
                "1 man + 1 woman in every shot; no third body in frame.",
                "HUSBAND_C is off-frame only: voice, phone text, wedding ring, adjoining door.",
                "No tattoo; the spade is a pendant prop, not body art.",
                "Consensual: green at P1.B02, Ready? at P2.B03, Take your time at P4.B05.",
                "One suite, five zones; no corridor or public space.",
                "Both leads must bind to CONFIRMED_ADULT/REVIEWED before explicit prompt derivation.",
                "Do not force a shot count; 122 is the current budget; every shot must map to an Event.",
                "No racial slurs, no degradation; the male lead is a full character.",
            ],
        },
        "art_direction": {
            "format": "anime-illustrated erotic weekend album, 5 parts, 8 beats each, 122 shots",
            "location": {"type": "hotel suite", "zones": ["living", "bedroom", "dining", "bathroom", "private terrace", "adjoining door"],
                         "continuity": "same suite across the weekend; city lights outside; warm interior lamps"},
            "costume": {"ladder": ["black evening dress", "black lingerie", "nude", "his white shirt", "white robe",
                                    "red dress", "travel clothes"],
                        "single_variable": "state of the outfit, not a new costume per beat"},
            "time": "Friday evening to Sunday morning",
        },
        "characters": [
            {"role_key": "WIFE_A", "character_id": None, "age_status": "UNKNOWN", "cast_status": "UNASSIGNED",
             "identity": "adult married woman; appearance TBD at bind; no tattoo; wedding ring",
             "appearance_evidence": "pending catalog bind; must be CONFIRMED_ADULT/REVIEWED"},
            {"role_key": "PARTNER_B", "character_id": None, "age_status": "UNKNOWN", "cast_status": "UNASSIGNED",
             "identity": "adult Black man; tall athletic; short black hair; trimmed beard; no tattoo; chef",
             "appearance_evidence": "pending catalog bind; must be CONFIRMED_ADULT/REVIEWED"},
            {"role_key": "HUSBAND_C", "character_id": None, "age_status": "UNKNOWN", "cast_status": "UNASSIGNED",
             "identity": "adult man; off-frame only",
             "appearance_evidence": "not required for frame; adult status still required for story context"},
        ],
        "acts": acts_plan,
    }
    rev = save_plan(con, story_id, plan)
    print("plan revision:", rev)

    state = {"story_id": story_id, "plan_revision": rev, "acts": {}, "beats": {}, "events": {}}
    for ai, act in enumerate(ACTS, 1):
        act_id = add_act(con, story_id, ai, act["title"], act["summary"], act["spec"])
        state["acts"][f"A{ai:02d}"] = act_id
        for bi, beat in enumerate(act["beats"], 1):
            beat_id = add_beat(con, act_id, bi, beat["summary"], {
                "purpose": beat["purposes"][0], "safety": beat["safety"], "shots": beat["shots"],
                "location_key": beat["location"], "prop_keys": beat["props"],
                "role_keys": beat["roles"], "moments": beat["moments"],
                "purposes": beat["purposes"], "cameras": beat["cameras"],
            })
            state["beats"][f"{act['spec']['part']}.B{bi:02d}"] = beat_id
            ev = beat["event"]
            event_id = add_event(con, beat_id, 1, {
                "actor_role_key": ev["actor"], "target_role_key": ev["target"],
                "action": ev["action"], "reaction": ev["reaction"],
                "raw_labels": LABELS, "source_fragment": beat["summary"],
                "spec": {**ev["spec"], "shot_budget": beat["shots"], "moments": beat["moments"],
                         "purposes": beat["purposes"], "cameras": beat["cameras"],
                         "location_key": beat["location"], "prop_keys": beat["props"],
                         "role_keys": beat["roles"]},
            })
            state["events"][f"{act['spec']['part']}.B{bi:02d}"] = event_id
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print("acts:", len(state["acts"]), "beats:", len(state["beats"]), "events:", len(state["events"]))

    # Draft storyboard (not saved).
    characters = {
        "WIFE_A": {"description": "adult married woman, appearance TBD at bind; elegant, medium-full build, wedding ring, no tattoo",
                   "provenance": "approved brief; blind placeholder", "character_id": None, "outfit_id": None},
        "PARTNER_B": {"description": "adult Black man, tall athletic, dark skin, short black hair, trimmed beard, no tattoo; chef",
                      "provenance": "approved brief; blind placeholder", "character_id": None, "outfit_id": None},
        "HUSBAND_C": {"description": "adult man, off-frame only: voice, phone text, wedding ring, adjoining door",
                      "provenance": "approved brief; blind placeholder", "character_id": None, "outfit_id": None},
    }
    locations = {
        "LOC_SUITE_LIVING": {"description": "hotel suite living area: black sofa, low table, champagne bucket, floor-to-ceiling window with city lights, warm lamp", "provenance": "approved brief"},
        "LOC_SUITE_BED": {"description": "hotel suite bedroom: king bed with black silk sheets, two nightstands, warm lamp, window with city lights", "provenance": "approved brief"},
        "LOC_SUITE_DINING": {"description": "suite dining corner: small table, two chairs, candle, wine, room service", "provenance": "approved brief"},
        "LOC_SUITE_BATH": {"description": "suite bathroom: deep tub, marble, mirror, warm light, towels", "provenance": "approved brief"},
        "LOC_SUITE_TERRACE": {"description": "private terrace: railing, two loungers, city skyline, daylight", "provenance": "approved brief"},
        "LOC_SUITE_DOOR": {"description": "suite entry and adjoining door: dark wood, brass handle, peephole, warm corridor light", "provenance": "approved brief"},
    }
    props = {
        "PROP_LUGGAGE": {"description": "small weekend bag, dark leather", "provenance": "approved brief"},
        "PROP_NOTE": {"description": "handwritten card on hotel stationery", "provenance": "approved brief"},
        "PROP_RING": {"description": "plain gold wedding ring", "provenance": "approved brief"},
        "PROP_PHONE": {"description": "smartphone with a dark screen", "provenance": "approved brief"},
        "PROP_DRESS": {"description": "black evening dress with a high slit", "provenance": "approved brief"},
        "PROP_CHAMPAGNE": {"description": "champagne bottle and two glasses", "provenance": "approved brief"},
        "PROP_PENDANT": {"description": "small silver spade pendant on a thin chain", "provenance": "approved brief; not a tattoo"},
        "PROP_DESSERT": {"description": "small dark dessert box tied with ribbon", "provenance": "approved brief"},
        "PROP_LINGERIE": {"description": "black lace lingerie", "provenance": "approved brief"},
        "PROP_RED_DRESS": {"description": "red evening dress with thin straps", "provenance": "approved brief"},
        "PROP_WINE": {"description": "red wine bottle and two glasses", "provenance": "approved brief"},
        "PROP_TOWEL": {"description": "white bath towel and robe", "provenance": "approved brief"},
        "PROP_BREAKFAST": {"description": "coffee cup, croissant, small tray", "provenance": "approved brief"},
        "PROP_TRAY": {"description": "room service tray with a folded tip", "provenance": "approved brief"},
    }
    styles = {"STYLE_ANIME": {"description": "clean anime illustration, cel shading, crisp lineart, warm amber interior and cool city night, readable faces, no dark vignette", "tone": "warm, intimate", "provenance": "approved brief"}}

    shots, coverage = [], []
    prev_key = None
    prev_loc = None
    k = 0
    for act in ACTS:
        for bi, beat in enumerate(act["beats"], 1):
            beat_key = f"{act['spec']['part']}.B{bi:02d}"
            beat_id = state["beats"][beat_key]
            event_id = state["events"][beat_key]
            for si in range(beat["shots"]):
                k += 1
                key = f"S{k:03d}"
                loc = beat["location"]
                if k == 1:
                    transition = "START"
                elif loc != prev_loc:
                    transition = beat["transition"] if beat["transition"] in ("LOCATION_CUT", "TIME_CUT", "BRANCH") else "LOCATION_CUT"
                else:
                    transition = beat["transition"] if beat["transition"] in ("CONTINUOUS", "CAMERA_CUT", "TIME_CUT") else "CAMERA_CUT"
                moment = beat["moments"][si]
                shots.append({
                    "shot_key": key, "shot_order": k, "beat_id": beat_id, "branch_key": "MAIN",
                    "previous_shot_key": prev_key, "transition": transition,
                    "purpose": beat["purposes"][si], "camera": beat["cameras"][si],
                    "focus": moment, "visual_moment": moment,
                    "role_keys": beat["roles"], "location_key": loc,
                    "prop_keys": beat["props"], "style_key": "STYLE_ANIME",
                })
                coverage.append({"event_id": event_id, "status": "VISUALIZED",
                                 "shot_key": key, "evidence": f"{key} shows: {moment}"})
                prev_key, prev_loc = key, loc

    board = {
        "story_revision": rev,
        "approval": {"status": "PENDING", "evidence": "Draft for user review; not saved to DB."},
        "visual_bible": {"characters": characters, "locations": locations, "props": props, "styles": styles},
        "shots": shots, "coverage": coverage,
    }
    (ROOT / "storyboard.draft.json").write_text(json.dumps(board, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Quà Kỷ Niệm — Storyboard draft", "",
             f"**Story:** `{story_id}`  |  **Plan revision:** {rev}  |  **Shots:** {len(shots)}  |  **Events:** {len(state['events'])}",
             "", "| # | Beat | Purpose | Camera | Moment |", "|---|---|---|---|---|"]
    for s in shots:
        beat_key = next((bk for bk, bid in state["beats"].items() if bid == s["beat_id"]), "")
        lines.append(f"| {s['shot_order']} | {beat_key} | {s['purpose']} | {s['camera']} | {s['visual_moment']} |")
    (ROOT / "storyboard.draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("draft shots:", len(shots), "events:", len(state["events"]))
    print("draft:", ROOT / "storyboard.draft.json")


if __name__ == "__main__":
    main()
