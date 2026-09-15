"""Gradio 界面（升级4：支持容器内 0.0.0.0 绑定）
员工端：上传发票自动抽取 + 提交报销 + 制度问答（带引用）
审批端：待审批列表 + 通过/驳回
"""
import os

import gradio as gr

from app.ui_handlers import (
    ask_question,
    do_transition,
    extract_invoice,
    pending_forms_text,
    submit_expense,
)


def _file_path(file_obj):
    """gradio File 组件在不同版本返回 str 或 FileData，统一取路径"""
    if isinstance(file_obj, str):
        return file_obj
    return getattr(file_obj, "name", file_obj)


def ui_extract(pdf_file):
    if pdf_file is None:
        return {}, "请先上传发票 PDF。"
    try:
        fields = extract_invoice(_file_path(pdf_file))
        return fields, "抽取完成，请核对字段后填城市提交。"
    except Exception as e:
        return {}, f"抽取失败：{type(e).__name__}: {e}"


def ui_submit(fields, city):
    return submit_expense(fields or {}, city or "")


def ui_transition(form_id, action, comment):
    try:
        fid = int(form_id)
    except (TypeError, ValueError):
        return "报销单 ID 必须是数字。"
    return do_transition(fid, action, comment or "")


with gr.Blocks(title="企业差旅报销 AI 助手") as demo:
    gr.Markdown("# 企业差旅报销 AI 助手")

    with gr.Tab("员工端"):
        gr.Markdown("### 提交报销（上传发票自动抽取）")
        pdf_file = gr.File(label="上传电子发票 PDF")
        extract_btn = gr.Button("抽取发票字段")
        extracted = gr.JSON(label="抽取结果")
        extract_info = gr.Textbox(label="提示", interactive=False)
        city = gr.Textbox(label="出差城市（差标校验用）", placeholder="如：北京")
        submit_btn = gr.Button("提交报销")
        submit_result = gr.Textbox(label="提交结果", lines=6)

        gr.Markdown("### 制度问答（带引用）")
        question = gr.Textbox(label="问题", placeholder="如：北京住宿标准是多少？")
        ask_btn = gr.Button("提问")
        answer = gr.Textbox(label="回答", lines=6)

    with gr.Tab("审批端"):
        gr.Markdown("流程：员工提交后为「草稿」，先选 submit 送入审批流，再 approve/reject。")
        refresh_btn = gr.Button("刷新待审批列表")
        pending = gr.Textbox(label="待审批报销单", lines=8)
        form_id = gr.Textbox(label="报销单 ID")
        action = gr.Dropdown(["submit", "approve", "reject"], label="操作")
        comment = gr.Textbox(label="审批意见")
        do_btn = gr.Button("执行")
        op_result = gr.Textbox(label="操作结果")

    extract_btn.click(ui_extract, [pdf_file], [extracted, extract_info])
    submit_btn.click(ui_submit, [extracted, city], [submit_result])
    ask_btn.click(ask_question, [question], [answer])
    refresh_btn.click(pending_forms_text, [], [pending])
    do_btn.click(ui_transition, [form_id, action, comment], [op_result])


if __name__ == "__main__":
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    )
