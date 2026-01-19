from ..analysis.collectors.ick_collector import IckCollector
from ..analysis.collectors.simp_collector import SimpCollector
from ..analysis.collectors.vibe_collector import VibeCollector
from ..persistence.repo import LoveRepo


class NoticeHandler:
    """通知事件处理器 (DDD Refactored)"""

    def __init__(self, repo: LoveRepo):
        self.repo = repo
        self.simp_col = SimpCollector()
        self.vibe_col = VibeCollector()
        self.ick_col = IckCollector()

    async def handle_notice(self, event_data: dict):
        if event_data.get("post_type") != "notice":
            return

        group_id = str(event_data.get("group_id", ""))
        user_id = str(event_data.get("user_id", ""))
        if not group_id:
            return

        # 1. 纯爱维度：戳一戳
        simp_m = self.simp_col.collect_notice(event_data)
        if simp_m["poke_sent"]:
            await self.repo.update_interaction_sent(group_id, user_id, poke=1)
            if simp_m["target_id"]:
                await self.repo.update_interaction_received(
                    group_id, simp_m["target_id"], poke=1
                )

        # 2. 存在感维度：表情回应
        vibe_m = self.vibe_col.collect_notice(event_data)
        if vibe_m["reaction_received"]:
            idx = await self.repo.get_message_owner(vibe_m["message_id"])
            if idx:
                await self.repo.update_interaction_sent(group_id, user_id, reaction=1)
                await self.repo.update_interaction_received(
                    group_id, idx.user_id, reaction=1
                )

        # 3. 败犬维度：撤回
        ick_m = self.ick_col.collect_from_notice(event_data)
        if ick_m["is_recall"]:
            await self.repo.update_interaction_sent(group_id, user_id, recall=1)
