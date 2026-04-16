from __future__ import annotations

from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1


def message_event(
    *,
    text: str,
    chat_id: str = "oc_test_chat",
    chat_type: str = "group",
    message_id: str = "om_test_message",
) -> P2ImMessageReceiveV1:
    return P2ImMessageReceiveV1(
        {
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_test_user"},
                    "sender_type": "user",
                    "tenant_key": "tenant",
                },
                "message": {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "message_type": "text",
                    "content": f'{{"text":"{text}"}}',
                },
            }
        }
    )
