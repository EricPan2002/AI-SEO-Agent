/**
 * 文章預覽卡片 + 發布到 WordPress。
 */

import type { Article, Outline, PublishResult } from '../types'

interface Props {
  outline: Outline
  article: Article
  isPublishing: boolean
  post?: PublishResult
  onPublish: () => void
}

export function PreviewCard({
  outline,
  article,
  isPublishing,
  post,
  onPublish,
}: Props) {
  return (
    <div className="card preview">
      <div className="preview-head">
        <h2 className="card-title">文章預覽</h2>
        <span className="badge">{article.word_count} 字</span>
      </div>

      <p className="meta-description">{outline.meta_description}</p>

      <div className="keyword-row">
        {outline.keywords_used.map((keyword) => (
          <span className="tag tag-static" key={keyword}>
            {keyword}
          </span>
        ))}
      </div>

      {/*
        使用 dangerouslySetInnerHTML 渲染 HTML。
        之所以安全，是因為這段 HTML 已經在後端經過 bleach 白名單過濾
        （見 backend/app/sanitize.py）——只留下 h1/h2/p/ul/li 等標籤，
        且不允許任何屬性，所以沒有 script、沒有事件處理器、沒有 style。
        絕不能直接把 LLM 的原始輸出丟進來，那等於把不可信內容當成可信內容。
      */}
      <article
        className="article-body"
        dangerouslySetInnerHTML={{ __html: article.html }}
      />

      <div className="preview-footer">
        {post ? (
          <div className="publish-success">
            <p>
              ✓ 草稿已建立（文章編號 {post.id}，狀態 {post.status}）
            </p>
            <a
              className="btn btn-primary"
              href={post.edit_link}
              target="_blank"
              rel="noreferrer"
            >
              在 WordPress 後台開啟
            </a>
          </div>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onPublish}
            disabled={isPublishing}
          >
            {isPublishing ? '發布中…' : '發布到 WordPress'}
          </button>
        )}
      </div>
    </div>
  )
}
