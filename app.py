import streamlit as st
import pandas as pd

# 页面基本配置
st.set_page_config(page_title="🀄 打牌计分神器", page_icon="🃏", layout="centered")

st.title("🃏 打牌/麻将计分神器")

# 初始化 Session State 以保存状态
if "setup_done" not in st.session_state:
    st.session_state.setup_done = False
    st.session_state.players = []
    st.session_state.scores = {}
    st.session_state.tea_pool = 0.0
    st.session_state.history = []
    st.session_state.tea_mode = "无"
    st.session_state.tea_rate = 0.0

# ================= 1. 游戏设置阶段 =================
if not st.session_state.setup_done:
    st.header("⚙️ 游戏初始化设置")
    
    # 玩家人数和名字
    num_players = st.slider("请选择玩家人数", min_value=3, max_value=6, value=4)
    players = []
    
    cols = st.columns(2)
    for i in range(num_players):
        with cols[i % 2]:
            name = st.text_input(f"玩家 {i+1} 昵称", value=f"玩家{i+1}", key=f"name_{i}")
            players.append(name)

    st.divider()
    
    # 茶水费设置
    st.subheader("☕ 茶水/饭钱设置")
    tea_mode = st.radio(
        "请选择茶水费收取模式：", 
        ["不设置茶水费", "赢家按比例抽水", "独立茶水池(自愿打款)"]
    )
    
    tea_rate = 0.0
    if tea_mode == "赢家按比例抽水":
        tea_rate = st.number_input("请输入抽水比例 (%)", min_value=0.0, max_value=100.0, value=5.0, step=1.0) / 100.0
        st.info(f"提示：每局赢家的利润中将有 {tea_rate*100}% 自动流入茶水池。")
    elif tea_mode == "独立茶水池(自愿打款)":
        st.info("提示：游戏开始后，玩家可以随时手动将自己的余额转入公共茶水池。")

    # 开始游戏按钮
    if st.button("🚀 开始游戏", use_container_width=True):
        if len(set(players)) != len(players):
            st.error("玩家名字不能重复，请修改！")
        else:
            st.session_state.players = players
            st.session_state.scores = {p: 0.0 for p in players}
            st.session_state.tea_mode = tea_mode
            st.session_state.tea_rate = tea_rate
            st.session_state.setup_done = True
            st.rerun()

# ================= 2. 游戏进行阶段 =================
if st.session_state.setup_done:
    # --- A. 顶部比分板 ---
    st.header("📊 当前战况")
    
    # 动态生成列（玩家人数 + 1个茶水池）
    score_cols = st.columns(len(st.session_state.players) + 1)
    for i, p in enumerate(st.session_state.players):
        score_cols[i].metric(label=p, value=round(st.session_state.scores[p], 2))
    
    # 突出显示茶水池
    score_cols[-1].metric(label="☕ 茶水池", value=round(st.session_state.tea_pool, 2))
    
    st.divider()

    # --- B. 每局记账表单 ---
    st.header("📝 记录新一局")
    with st.form("round_form"):
        st.write(f"**第 {len(st.session_state.history) + 1} 局**")
        round_scores = {}
        input_cols = st.columns(3)
        
        for i, p in enumerate(st.session_state.players):
            with input_cols[i % 3]:
                # 默认步长为 1，可以输入负数
                round_scores[p] = st.number_input(f"{p} 得分", value=0.0, step=10.0, format="%.1f")

        submitted = st.form_submit_button("✅ 提交本局", use_container_width=True)
        
        if submitted:
            # 校验总分是否为 0 (零和博弈)
            if round(sum(round_scores.values()), 2) != 0:
                st.error(f"⚠️ 账目不对！所有人得分总和必须为 0。当前总和为: {sum(round_scores.values())}")
            else:
                round_record = {"局数": len(st.session_state.history) + 1}
                round_tea = 0.0

                # 结算逻辑
                for p, score in round_scores.items():
                    actual_score = score
                    # 如果是赢家并且开启了按比例抽水
                    if score > 0 and st.session_state.tea_mode == "赢家按比例抽水":
                        water = score * st.session_state.tea_rate
                        actual_score = score - water
                        round_tea += water
                    
                    st.session_state.scores[p] += actual_score
                    round_record[p] = actual_score
                
                # 更新茶水池
                st.session_state.tea_pool += round_tea
                round_record["茶水费"] = round_tea

                # 记录历史
                st.session_state.history.append(round_record)
                st.success("✅ 记账成功！")
                st.rerun()

    # --- C. 独立茶水池打款功能 ---
    if st.session_state.tea_mode == "独立茶水池(自愿打款)":
        st.divider()
        st.subheader("💰 向茶水池打钱")
        with st.form("tea_fund_form"):
            t_cols = st.columns(2)
            contributor = t_cols[0].selectbox("打款人", st.session_state.players)
            amount = t_cols[1].number_input("金额", min_value=0.0, step=10.0)
            
            fund_submitted = st.form_submit_button("确认打入公共池")
            if fund_submitted and amount > 0:
                # 打款人分数减少，茶水池增加
                st.session_state.scores[contributor] -= amount
                st.session_state.tea_pool += amount
                
                # 记录这笔特殊账目
                st.session_state.history.append({
                    "局数": "茶水打赏",
                    contributor: -amount,
                    "茶水费": amount
                })
                st.rerun()

    st.divider()

    # --- D. 历史记录 ---
    st.header("📜 历史流水")
    if st.session_state.history:
        # 将历史记录转为 DataFrame 方便展示
        df = pd.DataFrame(st.session_state.history)
        
        # 确保列的顺序：局数、玩家名字、茶水费
        cols_order = ["局数"] + st.session_state.players + ["茶水费"]
        # 补全可能缺失的列（比如打赏记录里没出现的玩家设为0）
        for col in cols_order:
            if col not in df.columns:
                df[col] = 0.0
        df = df[cols_order].fillna(0)
        
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- E. 危险区 ---
    st.divider()
    if st.button("🔄 结束游戏并清空数据", type="primary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()