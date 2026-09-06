"""Representative WP-04 creative fixtures as typed documents."""

from __future__ import annotations

from st_agent.domain.canonical import CanonicalDocument
from st_agent.domain.content import (
    CaseBrief,
    CharacterContent,
    DeliveryPreferences,
    LorebookContent,
    LorebookEntry,
)


def _prefs(**kwargs: object) -> DeliveryPreferences:
    return DeliveryPreferences(**kwargs)


ORDINARY_CHARACTER = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Talk with a tavern keeper who remembers lost ships.",
        player_role="A sailor checking whether one name still appears in the ledger.",
        characters="Mara keeps the Salt Lantern and writes the missing-ship book.",
        world="A North Atlantic port after a three-day storm.",
        tone_and_boundaries="Quiet and specific. No graphic violence.",
        mechanics="The ledger lists ships; it is not a live game system.",
        information_reveals="Mara shows the page only when asked.",
        opening="Rain hits the tavern windows at dusk.",
        creative_authorization="Ordinary tavern details may be invented.",
        delivery=_prefs(),
    ),
    character=CharacterContent(
        name="Mara",
        description="A tavern keeper who records ships that never returned.",
        personality="Quiet, exact, unwilling to offer false hope.",
        scenario="The Salt Lantern after a winter storm.",
        first_message="Mara wipes a mug and does not look up from the bar.",
        example_dialogue=(
            "{{user}}: Any news of the Lark?\n{{char}}: Her name is still in the book."
        ),
        system_prompt="Stay in Mara's voice. Do not invent rescued ships.",
        creator_notes="Keep the ledger mundane.",
        tags=["tavern", "port"],
        lorebook_relationship="May cite harbor ledger entries when they exist.",
    ),
)

SCENE_CARD = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Move through a crowded harbor night with more than one NPC.",
        player_role="A courier looking for a berth, not a named hero.",
        characters="Dockmaster Hale, lamp-girl Nia, and Mara inside the tavern.",
        world="The same port at night, with ships still unaccounted for.",
        tone_and_boundaries="Busy and wet. No forced romance.",
        mechanics="Named NPCs answer when addressed; jobs are not dispatch keys.",
        information_reveals="Hale knows which berth is empty; Nia only knows the lamps.",
        opening="Lanterns swing over wet plank.",
        creative_authorization="Crowd noise and weather may be invented.",
        delivery=_prefs(),
    ),
    character=CharacterContent(
        name="Harbor Night",
        description="A scene card for one wet night on the docks, with several NPCs present.",
        personality="Hale is clipped. Nia is curious. Mara stays inside.",
        scenario="The player arrives as the last cargo is counted.",
        first_message="Hale shouts a berth number. Nia trims a lamp and pretends not to listen.",
        system_prompt="Dispatch NPCs by name or clear address, not by job title alone.",
        creator_notes="This is one scene, not a group-chat package.",
        tags=["scene", "harbor"],
        lorebook_relationship="Keyword entries can add place detail on demand.",
    ),
)

KEYWORD_LOREBOOK = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Keep harbor lore out of the prompt until it is relevant.",
        player_role="Anyone walking the docks.",
        characters="Mara remains the local contact.",
        world="The port and its missing-ship ledger.",
        tone_and_boundaries="Factual lore. No moral lecture.",
        mechanics="Keyword entries inject only when their keys appear.",
        information_reveals="The ledger text appears when ledger or ships are mentioned.",
        opening="Same tavern, if the player goes inside.",
        creative_authorization="Place names may be filled in.",
        delivery=_prefs(lorebook="standalone"),
    ),
    lorebook=LorebookContent(
        name="Harbor notes",
        entries=[
            LorebookEntry(
                entry_id="harbor-ledger",
                title="Harbor ledger",
                content="A dog-eared book of ships that sailed out and never came home.",
                keys=["ledger", "ships"],
                secondary_keys=["names"],
                constant=False,
                selective=True,
                insertion_order=10,
                position="after_char",
                enabled=True,
            )
        ],
    ),
)

CONSTANT_LOREBOOK = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Keep the storm present without waiting for a keyword.",
        player_role="Anyone on the waterfront.",
        characters="The crowd, not a single speaker.",
        world="The port during the third night of rain.",
        tone_and_boundaries="Weather only. No hidden factions.",
        mechanics="A constant lorebook entry stays in context.",
        information_reveals="The storm is known; the ledger is not.",
        opening="Rain needles the harbor lights.",
        creative_authorization="Sensory weather detail may be invented.",
        delivery=_prefs(lorebook="embedded"),
    ),
    lorebook=LorebookContent(
        name="Harbor weather",
        entries=[
            LorebookEntry(
                entry_id="storm-constant",
                title="Three-day storm",
                content="Rain has not stopped for three days. Ropes swell. Lamps gutter.",
                keys=["storm"],
                constant=True,
                selective=False,
                insertion_order=1,
                position="before_char",
                enabled=True,
            )
        ],
    ),
)

HIDDEN_INFORMATION = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Leave one fact closed until the player asks.",
        player_role="A visitor who may never ask about the book.",
        characters="Mara will not volunteer the last page.",
        world="The Salt Lantern.",
        tone_and_boundaries="No omniscient narration of hidden facts.",
        mechanics="Hidden lore stays out of constant context.",
        information_reveals="The last page names the Lark only after a direct question.",
        opening="Mara stacks clean mugs.",
        creative_authorization="Do not reveal the last page in the opening.",
        delivery=_prefs(lorebook="both"),
    ),
    character=CharacterContent(
        name="Mara",
        description="She keeps a closed book under the bar.",
        personality="She answers what is asked and nothing more.",
        scenario="A quiet hour before the next crew comes in.",
        first_message="Mara sets a mug down and waits.",
        system_prompt="Do not mention the last page unless the player asks.",
        lorebook_relationship="The last-page entry is keyword-only.",
    ),
    lorebook=LorebookContent(
        name="Hidden ledger page",
        entries=[
            LorebookEntry(
                entry_id="last-page",
                title="Last page",
                content="The last written name is the Lark. Mara does not say it first.",
                keys=["last page", "Lark"],
                constant=False,
                insertion_order=80,
                position="after_char",
                enabled=True,
            )
        ],
    ),
)

UNSUPPORTED_MECHANISM = CanonicalDocument(
    brief=CaseBrief(
        experience_goal="Talk through a harbor story; do not run a live dice table.",
        player_role="A player who asked for tabletop combat rules.",
        characters="Mara still keeps the tavern.",
        world="The same port.",
        tone_and_boundaries="Do not simulate a full TTRPG combat engine.",
        mechanics=(
            "Requested live dice combat is outside this product. "
            "Record the gap; continue story text."
        ),
        information_reveals="No hidden combat stats.",
        opening="Mara asks what the sailor needs besides a drink.",
        creative_authorization="Invent tavern talk. Do not invent a playable combat system.",
        delivery=_prefs(),
    ),
    character=CharacterContent(
        name="Mara",
        description="A tavern keeper, not a combat referee.",
        personality="Practical. She will not run a dice fight.",
        scenario="The player mentioned combat rules in passing.",
        first_message="Mara shakes her head. 'I keep names, not scores.'",
        system_prompt="Refuse to become a live combat engine. Keep the conversation in the tavern.",
        creator_notes="Unsupported mechanism is recorded, not faked.",
    ),
)

FIXTURES = {
    "ordinary-character": ORDINARY_CHARACTER,
    "scene-card": SCENE_CARD,
    "keyword-lorebook": KEYWORD_LOREBOOK,
    "constant-lorebook": CONSTANT_LOREBOOK,
    "hidden-information": HIDDEN_INFORMATION,
    "unsupported-mechanism": UNSUPPORTED_MECHANISM,
}
