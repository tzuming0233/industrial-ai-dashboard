with 채팅_영역:
    import ai_agent

    대화_목록 = 대화_목록_불러오기()
    if not 대화_목록:
        대화_생성()
        대화_목록 = 대화_목록_불러오기()
    대화_id_리스트 = [d["id"] for d in 대화_목록]
    대화_제목_맵 = {d["id"]: (d["제목"] or f"새 대화 ({d['생성일시'][:16]})") for d in 대화_목록}

    # "현재_대화_id"는 (다른 탭의 좁은 채팅 패널에서는) selectbox 위젯이 소유한 session_state
    # 키라 위젯이 이미 그려진 뒤에는 직접 대입할 수 없다 — 전환 요청은 별도 키에 잠시 담아뒀다가,
    # 위젯이 그려지기 전인 다음 런 시작 시점에 반영한다. (AI 채팅 탭의 사이드바 목록 클릭도
    # 동일한 방식을 그대로 써서 두 UI가 같은 session_state 키를 안전하게 공유하게 한다.)
    if "대화_전환_요청" in st.session_state:
        st.session_state["현재_대화_id"] = st.session_state.pop("대화_전환_요청")

    if 현재_탭_선택 == "AI 채팅":
        # AI 채팅 탭(전체화면)에서는 Claude AI처럼 왼쪽에 대화 목록 사이드바를 둔다.
        if st.session_state.get("현재_대화_id") not in 대화_id_리스트:
            st.session_state["현재_대화_id"] = 대화_id_리스트[0]
        현재_대화_id = st.session_state["현재_대화_id"]

        사이드바_영역, 채팅_메인 = st.columns([1, 3.2], gap="medium")
        with 사이드바_영역:
            if st.button("＋ 새 대화", use_container_width=True, type="primary"):
                새_id = 대화_생성()
                st.session_state["대화_전환_요청"] = 새_id
                st.session_state.pop("대기중_제안", None)
                st.session_state.pop("삭제확인_대화id", None)
                st.rerun()

            검색어 = st.text_input(
                "대화 검색", placeholder="🔍 대화 검색",
                label_visibility="collapsed", key="대화_검색어",
            )
            필터된_목록 = 대화_목록
            if 검색어.strip():
                _검색어_소문자 = 검색어.strip().lower()
                필터된_목록 = [
                    d for d in 대화_목록
                    if _검색어_소문자 in 대화_제목_맵.get(d["id"], "").lower()
                ]

            with st.container(height=420, border=False):
                if not 필터된_목록:
                    st.caption("검색 결과가 없습니다.")
                for d in 필터된_목록:
                    선택됨 = d["id"] == 현재_대화_id
                    라벨 = 대화_제목_맵.get(d["id"], str(d["id"]))
                    col_제목, col_삭제 = st.columns([5, 1])
                    if col_제목.button(
                        라벨, key=f"대화행_{d['id']}", use_container_width=True,
                        type="primary" if 선택됨 else "secondary",
                    ):
                        if not 선택됨:
                            st.session_state["대화_전환_요청"] = d["id"]
                            st.session_state.pop("대기중_제안", None)
                            st.session_state.pop("삭제확인_대화id", None)
                            st.rerun()
                    if col_삭제.button(
                        "🗑", key=f"대화삭제_{d['id']}", help="이 대화 삭제", use_container_width=True,
                    ):
                        st.session_state["삭제확인_대화id"] = d["id"]
                        st.rerun()

            if st.session_state.get("삭제확인_대화id") in 대화_id_리스트:
                _삭제대상_id = st.session_state["삭제확인_대화id"]
                st.warning(f"'{대화_제목_맵.get(_삭제대상_id, '')}' 대화를 삭제할까요? 되돌릴 수 없습니다.")
                확인_col1, 확인_col2 = st.columns(2)
                if 확인_col1.button("삭제", type="primary", key="대화삭제_확인버튼"):
                    대화_삭제(_삭제대상_id)
                    st.session_state.pop("삭제확인_대화id", None)
                    st.session_state.pop("현재_대화_id", None)
                    st.session_state.pop("대기중_제안", None)
                    st.rerun()
                if 확인_col2.button("취소", key="대화삭제_취소버튼"):
                    st.session_state.pop("삭제확인_대화id", None)
                    st.rerun()
    else:
        # 다른 탭의 좁은 사이드 채팅 패널: 사이드바를 놓을 공간이 없어 기존처럼 드롭다운으로 고른다.
        st.subheader("AI 에이전트")

        대화선택_col, 새대화_col, 삭제_col = st.columns([3, 1, 1])
        with 대화선택_col:
            현재_대화_id = st.selectbox(
                "대화 선택", options=대화_id_리스트,
                format_func=lambda id_: 대화_제목_맵.get(id_, str(id_)),
                label_visibility="collapsed", key="현재_대화_id",
            )
        with 새대화_col:
            if st.button("＋ 새 대화", use_container_width=True):
                새_id = 대화_생성()
                st.session_state["대화_전환_요청"] = 새_id
                st.session_state.pop("대기중_제안", None)
                st.session_state.pop("삭제확인_대화id", None)
                st.rerun()
        with 삭제_col:
            if st.button("🗑", use_container_width=True, help="이 대화 삭제"):
                st.session_state["삭제확인_대화id"] = 현재_대화_id
                st.rerun()

        if st.session_state.get("삭제확인_대화id") == 현재_대화_id:
            st.warning(f"'{대화_제목_맵.get(현재_대화_id, '')}' 대화를 삭제할까요? 되돌릴 수 없습니다.")
            확인_col1, 확인_col2 = st.columns(2)
            if 확인_col1.button("삭제", type="primary", key="대화삭제_확인버튼"):
                대화_삭제(현재_대화_id)
                st.session_state.pop("삭제확인_대화id", None)
                st.session_state.pop("현재_대화_id", None)
                st.session_state.pop("대기중_제안", None)
                st.rerun()
            if 확인_col2.button("취소", key="대화삭제_취소버튼"):
                st.session_state.pop("삭제확인_대화id", None)
                st.rerun()

        채팅_메인 = st.container()

    with 채팅_메인:
        채팅_높이 = 820 if 현재_탭_선택 == "AI 채팅" else 480
        채팅_컨테이너 = st.container(height=채팅_높이, border=True, key="채팅_상자")
        이전_기록 = 채팅기록_불러오기(현재_대화_id)
        with 채팅_컨테이너:
            if not 이전_기록:
                st.caption(
                    "예: '이번달 종료되는 사업은?' / '가나전자 사업을 완료 상태로 바꿔줘' — "
                    "엑셀·CSV·PDF·HWP 파일을 첨부(📎)하면 무조건 데이터로 반영하지 않고, "
                    "검토·상의가 필요한지 반영이 필요한지 먼저 판단합니다."
                )
            for 메시지 in 이전_기록:
                st.chat_message(메시지["role"]).write(메시지["content"])

            대기중_제안 = st.session_state.get("대기중_제안")
            if 대기중_제안:
                with st.chat_message("assistant"):
                    _제안_미리보기_표시(대기중_제안, 전체_df)
                    제안_col1, 제안_col2 = st.columns(2)
                    if 제안_col1.button("적용", type="primary", key="제안_적용_버튼"):
                        if 대기중_제안.get("유형") in ("업로드",):
                            백업_경로 = DB_PATH.with_name(f"실적관리_{_dt.datetime.now():%Y%m%d%H%M%S}.bak")
                            shutil.copy(DB_PATH, 백업_경로)
                        _제안_반영(대기중_제안, 전체_df)
                        st.session_state.pop("대기중_제안", None)
                        채팅기록_저장(현재_대화_id, "assistant", "반영했습니다.")
                        st.rerun()
                    if 제안_col2.button("취소", key="제안_취소_버튼"):
                        st.session_state.pop("대기중_제안", None)
                        채팅기록_저장(현재_대화_id, "assistant", "제안을 취소했습니다.")
                        st.rerun()

        입력 = st.chat_input(
            "질문을 입력하거나 파일을 첨부하세요",
            accept_file=True,
            file_type=["csv", "xlsx", "xls", "pdf", "hwp"],
        )

        if 입력:
            질문 = (입력.text or "").strip()
            첨부파일들 = list(입력.files) if 입력.files else []

            표시_메시지 = 질문
            if 첨부파일들:
                표시_메시지 = (표시_메시지 + f"\n\n📎 {첨부파일들[0].name}").strip()
            if 표시_메시지:
                첫_메시지_여부 = not 이전_기록
                with 채팅_컨테이너:
                    st.chat_message("user").write(표시_메시지)
                채팅기록_저장(현재_대화_id, "user", 표시_메시지)
                if 첫_메시지_여부:
                    대화_제목_설정(현재_대화_id, ai_agent.대화_제목_생성(표시_메시지))

            첨부_파일명 = 첨부파일들[0].name.lower() if 첨부파일들 else ""
            표_파일 = 첨부_파일명.endswith((".csv", ".xlsx", ".xls"))
            문서_파일 = 첨부_파일명.endswith((".pdf", ".hwp"))

            if 표_파일:
                with 채팅_컨테이너:
                    with st.chat_message("assistant"):
                        with st.spinner("AI가 파일을 살펴보는 중..."):
                            원본_df = _업로드_원본_읽기(첨부파일들[0])
                            if 원본_df.empty:
                                답변 = "첨부된 파일에서 데이터를 찾지 못했습니다."
                            else:
                                미리보기_행수 = min(8, len(원본_df))
                                합쳐진_질문 = (
                                    f"[첨부 파일 '{첨부파일들[0].name}' 미리보기 — 총 {len(원본_df)}행, "
                                    f"컬럼: {list(원본_df.columns)}]\n"
                                    f"{원본_df.head(미리보기_행수).to_csv(index=False)}"
                                    + (f"...(이하 {len(원본_df) - 미리보기_행수}행 생략)\n" if len(원본_df) > 미리보기_행수 else "")
                                    + f"\n[사용자 메시지]\n{질문 or '이 파일을 검토해줘.'}"
                                )
                                API용_기록 = [
                                    {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                                ]
                                결과 = ai_agent.질의하기(합쳐진_질문, history=API용_기록)
                                답변 = 결과["text"]
                                제안 = 결과.get("pending_action")
                                if 제안 and 제안.get("유형") == "import_uploaded_file_as_data":
                                    with st.spinner("AI가 사업현황 필드에 맞게 정리하는 중..."):
                                        매핑결과 = ai_agent.업로드_매핑_추론(
                                            list(원본_df.columns), 원본_df.head(5).to_dict("records")
                                        )
                                    if "오류" in 매핑결과:
                                        답변 += f"\n\n(반영 중 오류가 있었습니다: {매핑결과['오류']})"
                                    else:
                                        결과_df, 경고_목록 = _LLM_매핑_적용(원본_df, 매핑결과)
                                        st.session_state["대기중_제안"] = {
                                            "유형": "업로드", "결과_df": 결과_df, "경고": 경고_목록,
                                        }
                                elif 제안:
                                    st.session_state["대기중_제안"] = 제안
                        st.write(답변)
                채팅기록_저장(현재_대화_id, "assistant", 답변)
                st.rerun()
            elif 문서_파일:
                with 채팅_컨테이너:
                    with st.chat_message("assistant"):
                        with st.spinner("AI가 문서를 읽는 중..."):
                            try:
                                if 첨부_파일명.endswith(".pdf"):
                                    문서_텍스트 = _pdf_텍스트_추출(첨부파일들[0])
                                else:
                                    문서_텍스트 = _hwp_텍스트_추출(첨부파일들[0])
                            except Exception as e:
                                문서_텍스트 = None
                                답변 = f"'{첨부파일들[0].name}' 문서를 읽지 못했습니다: {e}"

                            if 문서_텍스트 is not None:
                                if not 문서_텍스트.strip():
                                    답변 = f"'{첨부파일들[0].name}'에서 텍스트를 추출하지 못했습니다(스캔 이미지 PDF일 수 있습니다)."
                                else:
                                    합쳐진_질문 = (
                                        f"[첨부 문서 '{첨부파일들[0].name}' 내용]\n{문서_텍스트}\n\n"
                                        f"[사용자 질문]\n{질문 or '이 문서 내용을 요약해줘.'}"
                                    )
                                    API용_기록 = [
                                        {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                                    ]
                                    결과 = ai_agent.질의하기(합쳐진_질문, history=API용_기록)
                                    답변 = 결과["text"]
                                    if 결과.get("pending_action"):
                                        st.session_state["대기중_제안"] = 결과["pending_action"]
                        st.write(답변)
                채팅기록_저장(현재_대화_id, "assistant", 답변)
                st.rerun()
            elif 질문:
                with 채팅_컨테이너:
                    with st.chat_message("assistant"):
                        with st.spinner("AI가 SQLite를 조회/제안하며 답변을 생성 중..."):
                            API용_기록 = [
                                {"role": m["role"], "content": m["content"]} for m in 이전_기록[-20:]
                            ]
                            결과 = ai_agent.질의하기(질문, history=API용_기록)
                        st.write(결과["text"])
                채팅기록_저장(현재_대화_id, "assistant", 결과["text"])
                if 결과.get("pending_action"):
                    st.session_state["대기중_제안"] = 결과["pending_action"]
                st.rerun()
