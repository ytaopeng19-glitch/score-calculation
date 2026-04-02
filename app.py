# --- 6. 快捷记账区域 ---
st.header("📝 提交分数")

# 初始化临时分数缓存，用于快捷按钮操作
if "temp_scores" not in st.session_state:
    st.session_state.temp_scores = {p: 0.0 for p in players}

# 定义快捷键增加分数的函数
def add_score(player, amount):
    st.session_state.temp_scores[player] += amount

# 清除当前输入
def reset_temp_scores():
    for p in players:
        st.session_state.temp_scores[p] = 0.0

st.write(f"正在录入第 **{current_round_num + 1}** 局")

# 使用列布局显示每个玩家的输入区
for p in players:
    with st.container():
        # 第一行：名字和手动输入框
        col_name, col_input = st.columns([1, 2])
        col_name.markdown(f"**{p}**")
        
        # 使用 key 绑定 session_state，实现按钮和输入框联动
        st.session_state.temp_scores[p] = col_input.number_input(
            f"分值 ({p})", 
            value=st.session_state.temp_scores[p],
            step=1.0,
            key=f"input_{p}",
            label_visibility="collapsed"
        )
        
        # 第二行：快捷按钮
        b1, b2, b3, b4 = st.columns(4)
        if b1.button(f"-10", key=f"m10_{p}"): add_score(p, -10); st.rerun()
        if b2.button(f"-5", key=f"m5_{p}"): add_score(p, -5); st.rerun()
        if b3.button(f"+5", key=f"p5_{p}"): add_score(p, 5); st.rerun()
        if b4.button(f"+10", key=f"p10_{p}"): add_score(p, 10); st.rerun()
    st.write("") # 间距

st.divider()

# 茶水费和提交按钮
col_tea, col_submit = st.columns([1, 1])
with col_tea:
    tea_fee_input = st.number_input("本局抽水 (茶水费)", value=0.0, step=5.0, min_value=0.0)

with col_submit:
    st.write("确认无误后提交")
    sub_btn = st.button("🚀 提交并同步全员", type="primary", use_container_width=True)
    if st.button("🧹 重置本局", use_container_width=True):
        reset_temp_scores()
        st.rerun()

# 提交逻辑
if sub_btn:
    # 获取当前所有输入的分数
    current_round_vals = st.session_state.temp_scores
    
    # 校验零和
    total_sum = sum(current_round_vals.values())
    if round(total_sum, 2) != 0:
        st.error(f"⚠️ 分数不平！当前总和：{total_sum} (必须为0)")
    else:
        # 构造存储数据
        details_to_save = {p: score for p, score in current_round_vals.items()}
        details_to_save["茶水费"] = tea_fee_input
        details_to_save["操作人"] = st.session_state.my_name
        
        # 写入 Supabase
        with st.spinner("同步中..."):
            supabase.table("game_rounds").insert({
                "room_id": room_id,
                "round_number": current_round_num + 1,
                "details": details_to_save
            }).execute()
        
        # 成功后重置输入并刷新
        reset_temp_scores()
        st.success("同步成功！")
        time.sleep(1)
        st.rerun()
