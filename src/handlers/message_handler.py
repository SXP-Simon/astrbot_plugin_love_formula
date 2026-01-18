from astrbot.api.event import AstrMessageEvent
from ..persistence.repo import LoveRepo
from ..models.tables import LoveDailyRef


class MessageHandler:
    def __init__(self, repo: LoveRepo):
        self.repo = repo

    async def handle_message(self, event: AstrMessageEvent):
        # Only process group messages
        if not event.message_obj.group_id:
            return

        group_id = event.message_obj.group_id
        user_id = event.message_obj.sender.user_id
        message_id = event.message_obj.message_id

        # 1. Save Message Index (for reaction attribution)
        await self.repo.save_message_index(message_id, group_id, user_id)

        # 2. Analyze Content
        text = event.message_str
        text_len = len(text)

        # Check for images
        image_count = 0
        for component in event.message_obj.message:
            if isinstance(component, dict) and component.get("type") == "image":
                image_count += 1
            elif (
                hasattr(component, "type") and component.type == "image"
            ):  # Object access
                image_count += 1

        # 3. Update Daily Stats
        await self.repo.update_msg_stats(
            group_id=group_id,
            user_id=user_id,
            text_len=text_len,
            image_count=image_count,
        )

        # TODO: Detect replies (Need to parse [CQ:reply] or Reply object)
