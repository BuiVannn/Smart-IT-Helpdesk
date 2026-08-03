import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { kbApi } from '@/api/kb'
import { Button, Field, LoadingBlock, inputClass } from '@/components/ui'

export function KbEditorPage() {
    const { slug } = useParams<{ slug?: string }>()
    const isEdit = !!slug
    const navigate = useNavigate()

    const [form, setForm] = useState({
        title: '', summary: '', contentMd: '', kbCategoryId: '', tags: '',
    })
    const [version, setVersion] = useState(0)

    const existing = useQuery({
        queryKey: ['kb', 'article', slug],
        queryFn: () => kbApi.getArticle(slug!),
        enabled: isEdit,
    })

    const categories = useQuery({
        queryKey: ['kb', 'categories'],
        queryFn: kbApi.listCategories,
    })

    useEffect(() => {
        if (existing.data) {
            const a = existing.data
            setForm({
                title: a.title, summary: a.summary ?? '',
                contentMd: a.contentMd, kbCategoryId: a.category?.id ?? '', tags: a.tags?.join(', ') ?? '',
            })
            setVersion(a.version)
        }
    }, [existing.data])

    const save = useMutation({
        mutationFn: () => isEdit
            ? kbApi.updateArticle(existing.data!.id, {
                ...form, kbCategoryId: form.kbCategoryId || undefined,
                tags: form.tags ? form.tags.split(',').map((t) => t.trim()) : [],
                version,
            })
            : kbApi.createArticle({
                ...form, kbCategoryId: form.kbCategoryId || undefined,
                tags: form.tags ? form.tags.split(',').map((t) => t.trim()) : [],
            }),
        onSuccess: (data) => navigate(`/kb/${data.slug}`),
        onError: (err: { status?: number }) => {
            if (err.status === 409)
                alert('Bài viết vừa được người khác sửa, hãy tải lại trang.')
        },
    })

    const publish = useMutation({
        mutationFn: async () => {
            const article = await save.mutateAsync()
            return kbApi.publishArticle(article.id)
        },
        onSuccess: (data) => navigate(`/kb/${data.slug}`),
        onError: (err: { status?: number }) => {
            if (err.status === 409)
                alert('Bài viết vừa được người khác sửa, hãy tải lại trang.')
        },
    })

    const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
        setForm((f) => ({ ...f, [key]: e.target.value }))

    if (isEdit && existing.isLoading) return <LoadingBlock />

    return (
        <div className="mx-auto max-w-2xl space-y-4">
            <h1 className="text-lg font-semibold text-slate-900">{isEdit ? 'Sửa bài viết' : 'Viết bài mới'}</h1>

            <form className="space-y-4 rounded-lg border border-slate-200 bg-white p-5"
                onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
                <Field label="Tiêu đề" htmlFor="title" required>
                    <input id="title" className={inputClass} value={form.title} onChange={set('title')} minLength={5} maxLength={200} required />
                </Field>
                <Field label="Tóm tắt" htmlFor="summary">
                    <input id="summary" className={inputClass} value={form.summary} onChange={set('summary')} />
                </Field>
                <Field label="Chủ đề" htmlFor="kbCategoryId">
                    <select id="kbCategoryId" className={inputClass} value={form.kbCategoryId} onChange={set('kbCategoryId')}>
                        <option value="">— Không chọn —</option>
                        {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                </Field>
                <Field label="Nhãn (phân cách bằng dấu phẩy)" htmlFor="tags">
                    <input id="tags" className={inputClass} value={form.tags} onChange={set('tags')} placeholder="wifi, email, vpn" />
                </Field>
                <Field label="Nội dung (Markdown)" htmlFor="contentMd" required>
                    <textarea id="contentMd" className={`${inputClass} h-64 font-mono text-sm`}
                        value={form.contentMd} onChange={set('contentMd')} minLength={20} required />
                </Field>

                {save.isError && (
                    <p className="text-sm text-red-600">Có lỗi xảy ra, vui lòng thử lại.</p>
                )}

                <div className="flex gap-2">
                    <Button type="submit" loading={save.isPending}>
                        {isEdit ? 'Lưu thay đổi' : 'Lưu nháp'}
                    </Button>
                    <Button type="button" variant="secondary"
                        loading={publish.isPending}
                        onClick={() => publish.mutate()}>
                        Đăng
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => navigate(-1)}>Huỷ</Button>
                </div>

            </form>
        </div>
    )
}
