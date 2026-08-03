import { api } from '@/api/client'
import type { ArticleListItem, ArticleDetail, KbCategory, Page } from '@/types'

export interface KbFilters {
    q?: string
    categoryId?: string
    tag?: string
    status?: string
    page?: number
}

function toQuery(filters: KbFilters): string {
    const params = new URLSearchParams()
    params.set('page', String(filters.page ?? 1))
    params.set('pageSize', '20')
    if (filters.q) params.set('q', filters.q)
    if (filters.categoryId) params.set('categoryId', filters.categoryId)
    if (filters.tag) params.set('tag', filters.tag)
    if (filters.status) params.set('status', filters.status)
    return params.toString()
}

export const kbApi = {
    listArticles: (filters: KbFilters) =>
        api.get<Page<ArticleListItem>>(`/kb/articles?${toQuery(filters)}`),

    getArticle: (slug: string) =>
        api.get<ArticleDetail>(`/kb/articles/${slug}`),

    createArticle: (input: { title: string; summary?: string; contentMd: string; kbCategoryId?: string; tags?: string[] }) =>
        api.post<ArticleDetail>('/kb/articles', input),

    updateArticle: (id: string, input: { title?: string; summary?: string; contentMd?: string; kbCategoryId?: string; tags?: string[]; version: number }) =>
        api.patch<ArticleDetail>(`/kb/articles/${id}`, input),

    publishArticle: (id: string) =>
        api.post<ArticleDetail>(`/kb/articles/${id}/publish`),

    unpublishArticle: (id: string) =>
        api.post<ArticleDetail>(`/kb/articles/${id}/unpublish`),

    listCategories: () =>
        api.get<KbCategory[]>('/kb/categories'),
}
