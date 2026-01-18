from astrbot.core.log import LogManager
from ..persistence.repo import LoveRepo

logger = LogManager.GetLogger("astrbot_plugin_love_formula")


class NoticeHandler:
    def __init__(self, repo: LoveRepo):
        self.repo = repo

    async def handle_notice(self, event_data: dict):
        """
        Handle raw notice events from NapCat/OneBot V11.
        AstrBot might expose raw data in event.
        """
        post_type = event_data.get("post_type")
        if post_type != "notice":
            return

        notice_type = event_data.get("notice_type")
        sub_type = event_data.get("sub_type")

        group_id = str(event_data.get("group_id", ""))
        user_id = str(event_data.get("user_id", ""))  # Operator

        if not group_id:
            return

        # 1. Poke (Notify)
        if notice_type == "notify" and sub_type == "poke":
            target_id = str(event_data.get("target_id", ""))
            # Sender poked Target
            await self.repo.update_interaction_sent(group_id, user_id, poke=1)
            await self.repo.update_interaction_received(group_id, target_id, poke=1)

        # 2. Reaction (Group Emoji Like)
        elif notice_type == "group_msg_emoji_like":
            message_id = str(event_data.get("message_id", ""))
            # Operator reacted to Message

            # Find who sent the message
            msg_idx = await self.repo.get_message_owner(message_id)
            if msg_idx:
                author_id = msg_idx.user_id
                # Operator sent reaction -> Author received reaction
                await self.repo.update_interaction_sent(group_id, user_id, reaction=1)
                await self.repo.update_interaction_received(
                    group_id, author_id, reaction=1
                )
            else:
                logger.debug(f"Reaction on unknown message {message_id}")

        # 3. Recall
        elif notice_type == "group_recall":
            # Operator recalled a message
            await self.repo.update_interaction_sent(group_id, user_id, recall=1)
