import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 页面配置 ---
st.set_page_config(page_title="🀄 全局同步计分系统 (Supabase版)", layout="centered")

# --- 1. 初始化 Supabase 连接 ---
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("🀄 棋牌实时同步计分系统")

# --- 2. 房间登录系统 ---
if "room_id" not in st.session_state:
    st.subheader("🔑 进入房间")
    room_input = st.text_input("请输入房间号 (如：8888)", placeholder="相同房间号数据互通")
    user_name = st.text_input("你的名字", placeholder="例如：张三")
    
    if st.button("进入房间", type="primary"):
        if room_input and user_name:
            st.session_state.room_id = room_input
            st.session_state.my_name = user_name
            st.rerun()
        else:
            st.error("请填入房间号和名字")
    st.stop()

# --- 3. 获取云端数据 ---
room_id = st.session_state.room_id

def get_room_data():
    # 从 Supabase 获取当前房间的所有对局数据，按局数升序排列
    response = supabase.table("game_rounds").select("*").eq("room_id", room_id).order("round_number").execute()
    return response.data

raw_data = get_room_data()

st.sidebar.info(f"🏠 当前房间：**{room_id}**\n\n👤 你的身份：**{st.session_state.my_name}**")
if st.sidebar.button("🔄 手动刷新比分"):
    st.rerun()

# --- 4. 数据解析与处理 ---
# 如果房间为空（没有任何数据）
if not raw_data:
    st.warning("本房间暂无玩家数据，请初始化房间。")
    st.subheader("⚙️ 初始化新房间")
    names_str = st.text_area("请输入所有玩家名字（用逗号或空格分隔）", placeholder="张三, 李四, 王五, 赵六")
    
    if st.button("创建房间记录"):
        # 处理玩家名字
        names = [n.strip() for n in names_str.replace("，", ",").replace(" ", ",").split(",") if n.strip()]
        if len(names) >= 3:
            # 构造第 0 局（初始状态）
            init_details = {name: 0.0 for name in names}
            init_details["茶水费"] = 0.0
            init_details["操作人"] = "系统初始化"
            
            # 写入 Supabase
            supabase.table("game_rounds").insert({
                "room_id": room_id,
                "round_number": 0,
                "details": init_details
            }).execute()
            
            st.success("房间创建成功！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("至少需要 3 名玩家才能开始。")
    st.stop()

# 解析 JSONB 数据为 DataFrame 方便计算和展示
history_list = []
players_set = set()

for row in raw_data:
    detail = row["details"]
    record = {"局数": row["round_number"]}
    for k, v in detail.items():
        record[k] = v
        if k not in ["茶水费", "操作人"]:
            players_set.add(k)
    history_list.append(record)

df_history = pd.DataFrame(history_list)
players = list(players_set)
current_round_num = max([row["round_number"] for row in raw_data])

# --- 5. 实时战况看板 ---
st.header("📊 实时战况")

# 计算当前得分（将所有局数的分数加起来）
current_scores = {p: df_history[p].sum() if p in df_history.columns else 0.0 for p in players}
tea_pool = df_history["茶水费"].sum() if "茶水费" in df_history.columns else 0.0

# 动态列展示
cols = st.columns(len(players) + 1)
for i, p in enumerate(players):
    cols[i].metric(p, round(current_scores[p], 2))
cols[-1].metric("☕ 茶水池", round(tea_pool, 2))

st.divider()

# --- 6. 记账表单 ---
st.header("📝 提交分数")
with st.form("add_round"):
    st.write(f"正在录入第 **{current_round_num + 1}** 局")
    round_input = {}
    input_cols = st.columns(3)
    
    for i, p in enumerate(players):
        with input_cols[i % 3]:
            # step=10.0 方便快速增减
            round_input[p] = st.number_input(f"{p} 得分", value=0.0, step=10.0, format="%.1f")
            
    tea_fee_input = st.number_input("本局扣除茶水费 (可选)", value=0.0, step=5.0, min_value=0.0)
    
    submitted = st.form_submit_button("✅ 提交并同步到云端", use_container_width=True)
    
    if submitted:
        # 校验零和：玩家分数总和 + 茶水费 应该等于 0 (或者单纯校验玩家总分)
        # 这里采用：玩家输入的得分总计必须为 0。茶水费是从某人赢的钱里单独拿出来的。
        if round(sum(round_input.values()), 2) != 0:
            st.error(f"⚠️ 分数总和必须为 0！当前总和：{sum(round_input.values())}")
        else:
            # 构造要存入 JSONB 的数据
            details_to_save = {p: score for p, score in round_input.items()}
            details_to_save["茶水费"] = tea_fee_input
            details_to_save["操作人"] = st.session_state.my_name
            
            # 写入 Supabase
            supabase.table("game_rounds").insert({
                "room_id": room_id,
                "round_number": current_round_num + 1,
                "details": details_to_save
            }).execute()
            
            st.success("同步成功！")
            time.sleep(1)
            st.rerun()

st.divider()

# --- 7. 历史流水明细 ---
st.header("📜 历史流水 (全员同步)")
# 整理一下列的顺序，让显示更美观
cols_order = ["局数"] + players + ["茶水费", "操作人"]
# 过滤掉第 0 局（初始化局）
display_df = df_history[df_history["局数"] > 0]

if not display_df.empty:
    display_df = display_df[cols_order].fillna(0)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("暂无打牌记录")
