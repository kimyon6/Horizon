from src.ai.article_text import extract_article_text, excerpt_from_feed_content


def test_extract_article_text_prefers_article_paragraphs_and_drops_noise() -> None:
    html = """
    <html><body>
      <nav>菜单和行情入口</nav>
      <article>
        <p>主流钢厂对焦炭开启首轮提降，湿熄焦下调五十元每吨。</p>
        <p>铁水产量回落，钢厂检修增加，焦炭现实需求继续承压。</p>
        <p>责任编辑：测试人员</p>
      </article>
      <footer>版权信息</footer>
    </body></html>
    """

    result = extract_article_text(html)

    assert "主流钢厂" in result
    assert "现实需求继续承压" in result
    assert "责任编辑" not in result
    assert "菜单" not in result


def test_feed_excerpt_rejects_google_title_only_boilerplate() -> None:
    content = (
        '<a href="https://news.google.com/item">焦炭首轮提降落地</a>'
        '<font color="#6f6f6f">新浪财经</font>'
    )

    assert excerpt_from_feed_content("焦炭首轮提降落地", content) is None


def test_feed_excerpt_keeps_and_limits_verbatim_source_text() -> None:
    content = "钢厂采购价下调五十五元每吨，焦企利润收缩，市场预计仍有后续提降压力。" * 20

    result = excerpt_from_feed_content("焦炭市场动态", content, limit=120)

    assert result is not None
    assert result.startswith("钢厂采购价下调五十五元每吨")
    assert len(result) <= 122
    assert result.endswith("……")
