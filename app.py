import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 页面配置 ---
st.set_page_config(page_title="🀄 棋牌同步计分系统", layout="centered")

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
    try:
        response = supabase.table("game_rounds").select("*").eq("room_id", room_id).order("round_number").execute()
        return response.data
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return []

raw_data = get_room_data()

st.sidebar.info(f"🏠 房间：**{room_id}** \n👤 身份：**{st.session_state.my_name}**")
if st.sidebar.button("🔄 刷新全员比分"):
    st.rerun()

# --- 4. 数据解析 ---
if not raw_data:
    st.warning("本房间暂无数据。")
    st.subheader("⚙️ 初始化新房间")
    names_str = st.text_area("输入所有玩家名字（用逗号或空格隔开）", placeholder="张三, 李四, 王五, 赵六")
    
    if st.button("创建房间"):
        names = [n.strip() for n in names_str.replace("，", ",").replace(" ", ",").split(",") if n.strip()]
        if len(names) >= 3:
            init_details = {name: 0.0 for name in names}
            init_details["茶水费"] = 0.0
            init_details["操作人"] = "系统初始化"
            supabase.table("game_rounds").insert({"room_id": room_id, "round_number": 0, "details": init_details}).execute()
            st.success("创建成功！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("至少需要 3 名玩家")
    st.stop()

# 解析历史数据
history_list = []
players_set = set()
for row in raw_data:
    detail = row["details"]
    record = {"局数": row["round_number"]}
    for k, v in detail.items():
        record[k] = v
        if k not in ["茶水费", "操作人"]: players_set.add(k)
    history_list.append(record)

df_history = pd.DataFrame(history_list)
players = sorted(list(players_set))
current_round_num = max([row["round_number"] for row in raw_data])

# --- 5. 实时战况看板 ---
st.header("📊 实时战况")
current_scores = {p: df_history[p].sum() for p in players}
tea_pool = df_history["茶水费"].sum() if "茶水费" in df_history.columns else 0.0

cols = st.columns(len(players) + 1)
for i, p in enumerate(players):
    cols[i].metric(p, round(current_scores[p], 2))
cols[-1].metric("☕ 茶水池", round(tea_pool, 2))

st.divider()

# --- 6. 下拉记账区域 ---
st.header("📝 提交分数")
st.write(f"正在录入第 **{current_round_num + 1}** 局")

# 定义分数选项
score_options = [0, 5, 10, 15, 20, 30, 40, 50, 100, -5, -10, -15, -20, -30, -40, -50, -100]
score_options.sort(reverse=True) # 从大到小排列

# 为每个玩家创建下拉框
current_round_input = {}
for p in players:
    # 每一个玩家对应一个独立的 selectbox
    current_round_input[p] = st.selectbox(
        f"玩家 **{p}** 的本局得分",
        options=score_options,
        index=score_options.index(0), # 默认为 0
        key=f"sb_{p}"
    )

st.write("")
t_col, s_col = st.columns([1, 1])
tea_val = t_col.number_input("本局抽水 (茶水费)", value=0.0, step=5.0)

# 提交按钮逻辑
if s_col.button("✅ 确认提交", type="primary", use_container_width=True):
    total = sum(current_round_input.values())
    
    # 校验：所有玩家得分相加必须为 0
    if round(total, 2) != 0:
        st.error(f"⚠️ 分数不平！当前所有人合计：{total}。请调整后再提交。")
    else:
        # 准备存入数据库的数据
        details = {p: s for p, s in current_round_input.items()}
        details["茶水费"] = tea_val
        details["操作人"] = st.session_state.my_name
        
        with st.spinner("正在同步数据..."):
            supabase.table("game_rounds").insert({
                "room_id": room_id, 
                "round_number": current_round_num + 1, 
                "details": details
            }).execute()
        
        st.success("记账成功！")
        time.sleep(0.5)
        st.rerun()

# 重置按钮（通过清除 session_state 中的 key）
if st.button("🧹 清空当前选择", use_container_width=True):
    for p in players:
        if f"sb_{p}" in st.session_state:
            del st.session_state[f"sb_{p}"]
    st.rerun()

st.divider()

# --- 7. 历史明细 ---
st.header("📜 历史流水")
display_df = df_history[df_history["局数"] > 0]
if not display_df.empty:
    cols_order = ["局数"] + players + ["茶水费", "操作人"]
    st.dataframe(display_df[cols_order].fillna(0), use_container_width=True, hide_index=True)
