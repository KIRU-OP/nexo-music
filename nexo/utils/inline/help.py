from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from nexo import app
from nexo.button_styles import danger_button, primary_button


TOTAL_SECTIONS = 33
BUTTON_LABEL_OVERRIDES = {
    25: "Dᴏᴡɴʟᴏᴀᴅ",
}


def generate_help_buttons(_, start: int, end: int, current_page: int):
    sections = list(range(start, end + 1))
    buttons = []

    # Keep a maximum of four buttons per row, while balancing the final
    # rows so a short last row does not stretch its buttons excessively.
    max_per_row = 4
    row_count = (len(sections) + max_per_row - 1) // max_per_row
    base_size, extra = divmod(len(sections), row_count)

    offset = 0
    for row_index in range(row_count):
        row_size = base_size + (1 if row_index < extra else 0)
        row = []
        for section in sections[offset : offset + row_size]:
            row.append(
                InlineKeyboardButton(
                    text=BUTTON_LABEL_OVERRIDES.get(section, _[f"H_B_{section}"]),
                    callback_data=f"help_callback hb{section}_p{current_page}",
                )
            )
        buttons.append(row)
        offset += row_size

    return buttons


def first_page(_):
    buttons = generate_help_buttons(_, 1, 15, current_page=1)
    buttons.append(
        [
            primary_button(text="ᴍᴇɴᴜ", callback_data="back_to_main"),
            primary_button(text="ɴᴇxᴛ", callback_data="help_next_2"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def second_page(_):
    buttons = generate_help_buttons(_, 16, TOTAL_SECTIONS, current_page=2)
    buttons.append(
        [
            primary_button(text="ʙᴀᴄᴋ", callback_data="help_prev_1"),
            primary_button(text="ᴍᴇɴᴜ", callback_data="back_to_main"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def action_sub_menu(_, current_page: int):
    return InlineKeyboardMarkup(
        [
            [
                primary_button(text=_["H_B_S_1"], callback_data="action_prom_1"),
                primary_button(text=_["H_B_S_2"], callback_data="action_pun_1"),
            ],
            [
                primary_button(
                    text=_["BACK_BUTTON"],
                    callback_data=f"help_back_{current_page}",
                )
            ],
        ]
    )


def help_back_markup(_, current_page: int):
    return InlineKeyboardMarkup(
        [
            [
                primary_button(
                    text=_["BACK_BUTTON"],
                    callback_data=f"help_back_{current_page}",
                ),
                danger_button(text=_["CLOSE_BUTTON"], callback_data="close"),
            ]
        ]
    )


def private_help_panel(_):
    return [
        [
            primary_button(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?start=help",
            )
        ]
    ]
