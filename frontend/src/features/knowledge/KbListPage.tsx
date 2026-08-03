import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { kbApi, type KbFilters } from '@/api/kb'
import { Button, EmptyState, ErrorState, LoadingBlock, inputClass } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { useDebounced } from '@/hooks/useDebounced'
import { cn } from '@/lib/utils'

const STATUS_STYLE: Record<string, string> = {
    PUBLISHED: 'bg-emerald-100 text-emerald-700',
    DRAFT: 'bg-slate-100 text-slate-600',
}
const STATUS_LABEL: Record<string, string> = {
    PUBLISHED: 'Đã đăng',
    DRAFT: 'Bản nháp',
}

export function KbListPage() {
    const { user } = useAuth()
    const canWrite = user?.role === 'ADMIN' || user?.role === 'IT_AGENT'

    const [search, setSearch] = useState('')
    const [filters, setFilters] = useState<KbFilters>({ page: 1 })
    const q = useDebounced(search)

    const articles = useQuery({
        queryKey: ['kb', 'articles', { ...filters, q }],
        queryFn: () => kbApi.listArticles({ ...filters, q }),
    })

    const categories = useQuery({
        queryKey: ['kb', 'categories'],
        queryFn: kbApi.listCategories,
    })

    const patch = (next: Partial<KbFilters>) =>
        setFilters((f) => ({ ...f, ...next, page: 1 }))

    return (
        <div className="space-y-4">
            <header className="flex flex-wrap items-center justify-between gap-3">
                <h1 className="text-lg font-semibold text-slate-900">Kho tài liệu</h1>
                {canWrite && (
                    <Link to="/kb/new">
                        <Button>Viết bài mới</Button>
                    </Link>

                )}
            </header>

            {/* Bộ lọc */}
            <div className="flex flex-wrap gap-2">
                <input
                    className={cn(inputClass, 'max-w-xs')}
                    placeholder="Tìm bài viết…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
                <select
                    className={cn(inputClass, 'max-w-[12rem]')}
                    value={filters.categoryId ?? ''}
                    onChange={(e) => patch({ categoryId: e.target.value || undefined })}
                >
                    <option value="">Mọi chủ đề</option>
                    {categories.data?.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                </select>
                {/* Chỉ Admin mới lọc theo trạng thái */}
                {user?.role === 'ADMIN' && (
                    <select
                        className={cn(inputClass, 'max-w-[10rem]')}
                        value={filters.status ?? ''}
                        onChange={(e) => patch({ status: e.target.value || undefined })}
                    >
                        <option value="">Mọi trạng thái</option>
                        <option value="PUBLISHED">Đã đăng</option>
                        <option value="DRAFT">Bản nháp</option>
                    </select>
                )}
            </div>

            {articles.isLoading && <LoadingBlock />}
            {articles.isError && <ErrorState error={articles.error} onRetry={() => articles.refetch()} />}

            {articles.data && articles.data.data.length === 0 && (
                <EmptyState
                    title="Chưa có bài viết nào"
                    hint={canWrite ? 'Hãy viết bài đầu tiên.' : 'Thử đổi từ khoá hoặc bộ lọc.'}
                />
            )}

            {articles.data && articles.data.data.length > 0 && (
                <div className="space-y-2">
                    {articles.data.data.map((article) => (
                        <Link
                            key={article.id}
                            to={`/kb/${article.slug}`}
                            className="block rounded-lg border border-slate-200 bg-white px-4 py-3 hover:border-blue-300 hover:shadow-sm transition"
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div>
                                    <p className="font-medium text-slate-900">{article.title}</p>
                                    {article.summary && (
                                        <p className="mt-0.5 text-sm text-slate-500 line-clamp-2">{article.summary}</p>
                                    )}
                                    <div className="mt-1 flex flex-wrap gap-1 text-xs text-slate-400">
                                        {article.category && <span>{article.category.name}</span>}
                                        {article.tags?.map((t) => <span key={t}>#{t}</span>)}
                                    </div>
                                </div>
                                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', STATUS_STYLE[article.status] ?? '')}>
                                    {STATUS_LABEL[article.status] ?? article.status}
                                </span>
                            </div>
                        </Link>
                    ))}
                </div>
            )}

            {/* Phân trang */}
            {articles.data && articles.data.pagination.totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 text-sm">
                    <Button variant="secondary" disabled={(filters.page ?? 1) <= 1}
                        onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}>
                        Trước
                    </Button>
                    <span className="text-slate-600">
                        Trang {articles.data.pagination.page} / {articles.data.pagination.totalPages}
                    </span>
                    <Button variant="secondary" disabled={(filters.page ?? 1) >= articles.data.pagination.totalPages}
                        onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}>
                        Sau
                    </Button>
                </div>
            )}
        </div>
    )
}
