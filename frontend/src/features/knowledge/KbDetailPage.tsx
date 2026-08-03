import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { kbApi } from '@/api/kb'
import { Button, ErrorState, LoadingBlock } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { formatDateTime } from '@/lib/utils'

export function KbDetailPage() {
    const { slug } = useParams<{ slug: string }>()
    const { user } = useAuth()
    const queryClient = useQueryClient()
    const canWrite = user?.role === 'ADMIN' || user?.role === 'IT_AGENT'

    const article = useQuery({
        queryKey: ['kb', 'article', slug],
        queryFn: () => kbApi.getArticle(slug!),
        enabled: !!slug,
    })

    const publish = useMutation({
        mutationFn: () => kbApi.publishArticle(article.data!.id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['kb'] }),
    })

    const unpublish = useMutation({
        mutationFn: () => kbApi.unpublishArticle(article.data!.id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['kb'] }),
    })

    if (article.isLoading) return <LoadingBlock />
    if (article.isError) return <ErrorState error={article.error} onRetry={() => article.refetch()} />
    if (!article.data) return null

    const a = article.data

    return (
        <div className="mx-auto max-w-3xl space-y-4">
            <div className="flex items-center justify-between gap-3">
                <Link to="/kb" className="text-sm text-slate-500 hover:text-slate-800">← Kho tài liệu</Link>
                {canWrite && (
                    <div className="flex gap-2">
                        <Link to={`/kb/${a.slug}/edit`}>
                            <Button variant="secondary">Sửa</Button>
                        </Link>

                        {a.status === 'PUBLISHED'
                            ? <Button variant="secondary" loading={unpublish.isPending} onClick={() => unpublish.mutate()}>Gỡ bài</Button>
                            : <Button loading={publish.isPending} onClick={() => publish.mutate()}>Đăng bài</Button>
                        }
                    </div>
                )}
            </div>

            <article className="rounded-lg border border-slate-200 bg-white p-6">
                <h1 className="text-2xl font-bold text-slate-900">{a.title}</h1>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-400">
                    {a.category && <span>{a.category.name}</span>}
                    <span>{a.viewCount} lượt xem</span>
                    {a.publishedAt && <span>Đăng ngày {formatDateTime(a.publishedAt)}</span>}
                    {a.author && <span>Tác giả: {a.author.fullName}</span>}
                </div>
                {a.summary && <p className="mt-3 text-slate-600">{a.summary}</p>}
                <div className="prose mt-6 max-w-none">
                    <ReactMarkdown>{a.contentMd}</ReactMarkdown>
                </div>
            </article>
        </div>
    )
}
