from __future__ import annotations

"""seed_writing_factors.py — 一次性将报告 C 节写作因子种入 factors 表。

运行:
    python scripts/seed_writing_factors.py [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("seed_writing_factors")

# ---------------------------------------------------------------------------
# 因子数据 — 来源: 04-report.md § C. 写作因子候选
# dimension 映射:
#   去AI味类  → rhetoric (词/句式/内容层面修辞技法)
#   钩子类    → opening  (标题 & 开头钩子)
#   传播类    → structure (内容结构与情绪设计)
#   CTA类     → closing   (结尾转化)
#   节奏/句式 → rhythm
#   排版      → layout
# ---------------------------------------------------------------------------

WRITING_FACTORS: list[dict] = [
    # ── 去AI味类 ──────────────────────────────────────────────────────────
    {
        "name": "排序词口语化",
        "dimension": "rhetoric",
        "technique": (
            "将「首先/其次/最后」等排序词替换为个人思维轨迹表达，"
            "整篇排序词出现不超过 1 次。"
        ),
        "anti_example": "首先，我们来看第一个问题。其次，需要注意的是……最后，总结一下。",
        "example_text": "起初我觉得这没什么难度。后来才发现完全不是那回事。现在才明白，问题根本出在另一层。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "书面大词清洗",
        "dimension": "rhetoric",
        "technique": (
            "删除或替换「显而易见/不言而喻/毋庸置疑/鉴于/相应地/众所周知/让我们」"
            "及非必要行业黑话（矩阵/赋能/生态链路/输出），换成大白话。"
        ),
        "anti_example": "显而易见，这套方案能够全面赋能企业生态链路的输出效率。",
        "example_text": "说白了，这套方案就是让团队少走弯路、多出结果。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "不确定性降级",
        "dimension": "rhetoric",
        "technique": (
            "将绝对表述降级：「所有人都」→「大多数/不少人」；"
            "「必然导致」→「往往会/可能造成」；「是事实」→「据说/似乎如此」。"
            "同时主动撒入模糊语气词：其实、说实话、大概、还挺、有点、好像。"
        ),
        "anti_example": "所有人都知道，这必然导致效率大幅提升，这是事实。",
        "example_text": "大多数人其实都有过这种感觉，好像事情往往会在最意想不到的时候好转。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "长短句交替",
        "dimension": "rhythm",
        "technique": (
            "每段混排 8-10 字短句与 20-25 字长句；允许单句成段；"
            "每篇至少 1 处疑问句、1 处感叹句；主动语态不低于 60%，被动语态不超 20%。"
        ),
        "anti_example": "这个方法可以帮助我们提升工作效率，同时也能改善团队协作，从而达到更好的结果。",
        "example_text": "说实话，我也不确定。但就是那次意外的决定，让整个项目彻底活了。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "句子开头多样化",
        "dimension": "rhythm",
        "technique": (
            "交替用状语、介词短语、口语词（「哎呀」「你看」「说真的」）起句首，"
            "禁止全部以主语开头；用破折号、省略号在句中打断节奏。"
        ),
        "anti_example": "这个问题很重要。这个方法很有效。这个结果很令人满意。",
        "example_text": "说真的，我当时根本没想到会这样——结果反而出人意料地好。你看，有时候放手才是最好的选择。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "自我纠正句",
        "dimension": "rhetoric",
        "technique": (
            "在转折处植入自我纠正：「等等，我说反了……」"
            "「不对，应该这样理解……」「其实我刚才那句不太准确」。"
            "配合「起初以为 X，后来发现 Y」的认知翻转结构。"
        ),
        "anti_example": "这个方法非常高效，能够帮助用户快速达成目标，提升整体满意度。",
        "example_text": "等等，我刚才说「快速」——其实这里要更正一下，真正有效的方式往往反而需要慢下来。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "认知翻转结构",
        "dimension": "structure",
        "technique": (
            "用「起初以为 X，后来发现 Y」结构呈现认知翻转；"
            "先抛出反常识结论，再回溯解释原因，制造阅读惊喜。"
        ),
        "anti_example": "很多人认为多读书就能提升写作能力，这是有道理的，因为积累很重要。",
        "example_text": "起初我以为多读书就能写好文章。后来发现，读了十年书、写出来还是一坨的人多了去了。真正的关键，是刻意练习输出。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "人设四件套",
        "dimension": "rhetoric",
        "technique": (
            "写作前固定人设四件套：{角色}+{立场}+{交流对象}+{情绪基调}。"
            "全文用第一人称「我/我们」，明确表态（我不同意……/这让我很震撼/说实话我有点怀疑）。"
        ),
        "anti_example": "本文将客观分析当前市场趋势，为读者提供全面的参考视角。",
        "example_text": "说实话，我对这个结论有点怀疑。作为一个在这行摸爬滚打了五年的人，我觉得数据背后的故事比数据本身更值得看。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "非线性段落逻辑",
        "dimension": "structure",
        "technique": (
            "打破「总-分-总/先观点后论据」的线性结构，改用："
            "由果推因 / 先讲场景案例再收口 / 先抛反常识结论再回溯。"
            "反直觉内容前置。"
        ),
        "anti_example": "本文主要讲三点：一是……二是……三是……综上所述，这三点共同构成了完整的解决方案。",
        "example_text": "那天我的账号掉了一半粉。不是因为内容变差了，而是因为我改了一个「小细节」——后来我才搞清楚为什么这个改动这么致命。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "情绪具名感官化",
        "dimension": "rhetoric",
        "technique": (
            "先点名情绪（挫败/兴奋/焦虑），再用感官细节接住；"
            "抽象形容词换可感知描述（视觉/触觉/听觉）。"
        ),
        "anti_example": "山顶日出很美，让人感到心旷神怡，整个人都放松了。",
        "example_text": "日出把天烧成橙红和粉，清晨冷空气灌进肺里，寂静是对你早起的奖赏。那一刻，所有的疲惫都值了。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "引用去模板化",
        "dimension": "rhetoric",
        "technique": (
            "引用不统一格式，带模糊记忆感和个人评价："
            "「某某在《XXX》里提到过……」「据我记得看过一篇论文说……」"
            "「有人主张 X，但我不太同意」。"
        ),
        "anti_example": "研究表明，根据相关文献记载，这一现象普遍存在于各类群体之中。",
        "example_text": "记得好像是在哪篇论文里看到过——说是人们转发内容主要不是因为内容好，而是因为转发这个动作让自己看起来更聪明。我当时觉得这话有点刻薄，但后来越想越觉得是真的。",
        "status": "active",
        "source_type": "manual",
    },
    # ── 钩子类 ────────────────────────────────────────────────────────────
    {
        "name": "缺口甜区标题",
        "dimension": "opening",
        "technique": (
            "标题让读者秒懂「话题是什么」但不知道「结论是什么」；"
            "悬念必须带具体锚点（禁纯「你绝想不到」），"
            "好奇缺口「甜区」=揭话题不揭答案。"
        ),
        "anti_example": "你绝对想不到这个方法的效果有多神奇",
        "example_text": "我停用了话题标签，触达翻了 3 倍",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "损失厌恶框架",
        "dimension": "opening",
        "technique": (
            "优先用损失厌恶而非收益框架构建标题和开头："
            "「别再/千万不要/警惕」比「学会…技巧/获得…好处」打开率高约 15%。"
        ),
        "anti_example": "学会这 5 个技巧，提升你的写作能力",
        "example_text": "别再犯这 5 个错误，你的文章一直没人看就是因为它们",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "数字锚点",
        "dimension": "opening",
        "technique": (
            "标题和关键句中至少含 1 个具体数字，禁用「很多/大量/若干」；"
            "用精确数字对比（1 小时 vs 5 年 / 3 倍 / 90%）强化可信度和好奇心。"
        ),
        "anti_example": "我做了这个改变，效果好了很多",
        "example_text": "我每天只写 20 分钟，坚持 90 天后粉丝从 200 涨到 12000",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "人群对号入座",
        "dimension": "opening",
        "technique": (
            "标题和开篇嵌入可识别的人群/场景标签（年龄/职业/地区/身份词），"
            "让目标读者在 0.5 秒内判断「这是写给我的」。"
        ),
        "anti_example": "如何调整心态找工作",
        "example_text": "应届生如何调整心态，找到第一份心仪工作",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "开头三模板",
        "dimension": "opening",
        "technique": (
            "开篇三选一：\n"
            "① 未命名的「那一个」——「有一个习惯，把 6 位数博主和普通人分开」\n"
            "② 反直觉结果——「我停用了 X，结果 Y 翻倍」\n"
            "③ 条件式威胁——「如果你正在这么做，你的账号正在受损」\n"
            "前 50 字内必须出现【悬念/数据/故事】至少一种。"
        ),
        "anti_example": "今天给大家分享一些关于公众号运营的经验和技巧，希望对大家有所帮助。",
        "example_text": "有一个习惯，把 6 位数博主和普通人分开。不是发稿频率，不是选题，而是一件每次写完都会做的「小事」。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "段落钩子",
        "dimension": "opening",
        "technique": (
            "正文每约 300 字埋一个新钩子（悬念/反转/未答问题/小标题），"
            "段落结尾给读者继续读的理由："
            "「但真正的问题在下面」「更关键的是第 3 点」。"
        ),
        "anti_example": "以上就是这一点的全部内容，下面我们来看第二点。",
        "example_text": "这只是表面原因。更关键的是第 3 点——很多人知道却从不去做，那才是拉开差距的地方。",
        "status": "active",
        "source_type": "manual",
    },
    # ── 传播类 ────────────────────────────────────────────────────────────
    {
        "name": "awe认知冲击",
        "dimension": "structure",
        "technique": (
            "目标情绪锁定敬畏/惊叹(awe)、愤怒、焦虑等高唤起情绪；"
            "主动避开悲伤（低唤起，转发率低）。"
            "多用「原来如此/没想到吧」式认知冲击——反直觉事实、宏大视角、惊叹的因果链。"
        ),
        "anti_example": "这件事让人感到很遗憾，我们应该为此感到悲伤并深刻反思。",
        "example_text": "没想到吧——全球转发量最高的文章，情绪不是感动，是愤怒。Berger 在沃顿的研究发现：愤怒让人「坐不住想立刻分享」，而悲伤让人只想静静待着。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "身份金句",
        "dimension": "structure",
        "technique": (
            "每篇提炼 1-2 个「身份宣言式金句」（立场/价值观/圈层标签），"
            "加粗放在易截图位置；"
            "读者转发=表态=标记自己是圈内人。"
        ),
        "anti_example": "写作是一项重要的技能，值得我们认真对待和不断练习。",
        "example_text": "**做新媒体的人，最大的自我欺骗，是把「发出去」当成「做完了」。**",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "故事容器",
        "dimension": "structure",
        "technique": (
            "不干堆事实/统计，把方法论包进「人物-冲突-转折」小故事；"
            "信息在「闲聊」伪装下传播——people don't share statistics, they share stories。"
        ),
        "anti_example": "研究表明，长期坚持阅读可以提升认知能力，增强词汇量，改善专注力，有助于情绪管理。",
        "example_text": "我有个朋友，每天通勤 1 小时，用来刷短视频。直到有一天他被裁员，发现自己没有任何可以写进简历的新技能——那一年他刷了 3000 小时的视频。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "触发器绑定",
        "dimension": "structure",
        "technique": (
            "选题/关键词绑定高频日常场景（周一、通勤、发工资、点外卖、开会），"
            "让环境一出现就联想到内容，延长长尾传播。"
        ),
        "anti_example": "今天分享一些关于时间管理的小技巧。",
        "example_text": "每个周一早上挤地铁的时候，你有没有想过：这一周，你打算在哪件事上真正往前走一步？",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "利他点名",
        "dimension": "structure",
        "technique": (
            "显式点名转发受益人群，把利他从隐性变显性，降低读者的分享决策成本："
            "「转给正在带娃的朋友」「发给团队新人」。"
        ),
        "anti_example": "如果觉得有用的话，欢迎点赞转发。",
        "example_text": "如果你身边有正在找第一份工作的朋友，把这篇转给他——比任何祝福都实用。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "圈层黑话",
        "dimension": "structure",
        "technique": (
            "用圈层专属表达制造归属感和圈内人认同："
            "「做新媒体的都懂」「当过班主任的看完都笑了」；"
            "转发=帮同类+标记自己是圈内人。"
        ),
        "anti_example": "很多职场人都能理解这种感觉，这在工作中是很常见的现象。",
        "example_text": "做过内容运营的都懂那种感觉：数据不好的时候，每刷新一次后台，心就往下沉一次。",
        "status": "active",
        "source_type": "manual",
    },
    # ── CTA类 ─────────────────────────────────────────────────────────────
    {
        "name": "单一CTA",
        "dimension": "closing",
        "technique": (
            "结尾只放一个行动指令，删掉所有竞争性按钮/链接；"
            "关注/领资料/评论三选一，放在读者情绪最高点之后。"
            "单一 CTA 比多 CTA 转化高最多 266%。"
        ),
        "anti_example": "喜欢就点赞，觉得有用就收藏，欢迎转发，也别忘了关注我们，有问题在评论区留言。",
        "example_text": "如果这篇对你有用，关注一下——我每周都会更新这类干货，下次不用碰运气找。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "第一人称CTA",
        "dimension": "closing",
        "technique": (
            "CTA 用第一人称「我」替代「你」，配合强动词："
            "「立即关注」→「我要每周收到职场干货」；"
            "「领取」→「把模板发给我」。"
            "「my」替「your」点击率高 90%，第一人称最高 +202%。"
        ),
        "anti_example": "立即关注我们，了解更多精彩内容。",
        "example_text": "我要每周收到一篇这样的干货——关注后回复「干货」，我帮你整理好发过来。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "福利钩子绑关注",
        "dimension": "closing",
        "technique": (
            "CTA 绑定即时福利钩子，且钩子要贴本篇内容："
            "「关注后回复【关键词】领〈具体资料〉」；"
            "裸二维码远不如带引导语的二维码有效。"
        ),
        "anti_example": "扫码关注我们的公众号。",
        "example_text": "关注后回复「周报」，领我整理的《10 分钟写完周报模板》，这周就能用上。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "紧迫稀缺",
        "dimension": "closing",
        "technique": (
            "CTA 加入紧迫感或稀缺感阻止二次犹豫："
            "「本周有效/前 100 名/下周删除/今天截止」。"
        ),
        "anti_example": "感兴趣的朋友可以关注一下，随时都能领取。",
        "example_text": "关注后回复「模板」即可领取，本周五 24:00 下架，之后不再提供。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "四选一收口",
        "dimension": "closing",
        "technique": (
            "结尾必须有明确收口，四选一：\n"
            "① 总结+再强调核心观点\n"
            "② 金句升华\n"
            "③ 抛话题引发评论互动\n"
            "④ 下期预告制造期待\n"
            "收口后紧接关注引导，绝不戛然而止。"
        ),
        "anti_example": "好了，今天就分享到这里，希望对大家有帮助，再见。",
        "example_text": "最后问一句：你现在正在用的写作方法，是自己摸索的，还是有人教的？评论区聊聊——我很好奇那些写得好的人，起点都是什么。",
        "status": "active",
        "source_type": "manual",
    },
    {
        "name": "推荐语五件套",
        "dimension": "closing",
        "technique": (
            "关注引导前配一句推荐语，消除陌生感，说清五件事："
            "我是谁 / 解决什么问题 / 什么调性 / 给谁看 / 有何背书。"
            "「对未知事物人们普遍拒绝」，先消疑虑再促关注。"
        ),
        "anti_example": "欢迎关注我的公众号，获取更多精彩内容。",
        "example_text": "我是一个做了 6 年公众号的内容人，专门研究「写出来有人看」这件事。每周一篇，不水、不废话、不卖课。如果你也在为内容头疼，我们可以一起想——关注一下，看看合不合口味。",
        "status": "active",
        "source_type": "manual",
    },
]


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------


def seed(session, *, dry_run: bool = False) -> dict:
    """将 WRITING_FACTORS 种入数据库（幂等）。

    Args:
        session: SQLAlchemy Session。
        dry_run: 为 True 时只打印将要插入的因子，不实际写入。

    Returns:
        {"inserted": int, "skipped": int}
    """
    from app.models.factor import Factor
    from sqlalchemy import select

    existing_names: set[str] = set()
    existing = session.scalars(select(Factor.name)).all()
    existing_names = set(existing)

    to_insert = [f for f in WRITING_FACTORS if f["name"] not in existing_names]
    to_skip = [f for f in WRITING_FACTORS if f["name"] in existing_names]

    if dry_run:
        if to_insert:
            logger.info("[dry-run] Would insert %d factor(s):", len(to_insert))
            for f in to_insert:
                logger.info("  + %s (%s)", f["name"], f["dimension"])
        else:
            logger.info("[dry-run] Nothing to insert; all %d factor(s) already exist.", len(to_skip))
        return {"inserted": 0, "skipped": len(to_skip)}

    for data in to_insert:
        factor = Factor(
            name=data["name"],
            dimension=data["dimension"],
            technique=data["technique"],
            anti_example=data.get("anti_example"),
            example_text=data.get("example_text"),
            status=data.get("status", "active"),
            source_type=data.get("source_type", "manual"),
        )
        session.add(factor)

    session.flush()
    logger.info("Inserted %d factor(s), skipped %d (already exist).", len(to_insert), len(to_skip))
    return {"inserted": len(to_insert), "skipped": len(to_skip)}


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Seed writing factors into the database.")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be inserted without writing.")
    args = parser.parse_args()

    try:
        from app.db.session import get_session_factory
    except Exception as exc:
        logger.error("Failed to import app modules: %s", exc)
        sys.exit(1)

    try:
        session_factory = get_session_factory()
    except Exception as exc:
        logger.error("Failed to create session factory (check DATABASE_URL): %s", exc)
        sys.exit(1)

    session = session_factory()
    try:
        result = seed(session, dry_run=args.dry_run)
        if not args.dry_run:
            session.commit()
        logger.info("Done: %s", result)
    except Exception as exc:
        session.rollback()
        logger.error("Seed failed: %s", exc)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
