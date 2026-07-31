import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { ApiError } from '@/api/client'
import { Button, Field, inputClass } from '@/components/ui'
import { PRIORITY_OPTIONS } from './badges'
import { useCreateTicket } from './hooks'
import type { TicketPriority } from '@/types'

/**
 * Ràng buộc PHẢI khớp CHECK constraint của database (title 5–200,
 * description 10–5000). Lệch nhau thì người dùng gõ xong, bấm gửi, rồi mới
 * nhận lỗi từ server — thay vì biết ngay lúc đang gõ.
 */
const schema = z.object({
  title: z
    .string()
    .trim()
    .min(5, 'Tiêu đề phải từ 5 ký tự')
    .max(200, 'Tiêu đề tối đa 200 ký tự'),
  description: z
    .string()
    .trim()
    .min(10, 'Mô tả phải từ 10 ký tự — hãy nêu rõ sự cố để IT xử lý nhanh hơn')
    .max(5000, 'Mô tả tối đa 5000 ký tự'),
  priority: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

export function CreateTicketPage() {
  const navigate = useNavigate()
  const createTicket = useCreateTicket()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', description: '', priority: '' },
  })

  const description = watch('description') ?? ''

  async function onSubmit(values: FormValues) {
    const ticket = await createTicket.mutateAsync({
      title: values.title,
      description: values.description,
      // Để trống thì backend lấy mặc định theo loại sự cố, và AI sẽ phân loại lại
      priority: (values.priority || null) as TicketPriority | null,
    })
    navigate(`/tickets/${ticket.id}`, { replace: true })
  }

  const submitError = createTicket.error

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Tạo yêu cầu hỗ trợ</h1>
      <p className="mb-6 text-sm text-slate-500">
        Mô tả càng cụ thể, đội IT càng xử lý nhanh. Hệ thống sẽ tự phân loại sự cố.
      </p>

      {submitError && (
        <div role="alert" className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {submitError instanceof ApiError
            ? submitError.message
            : 'Không gửi được yêu cầu. Vui lòng thử lại.'}
        </div>
      )}

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="rounded-lg border border-slate-200 bg-white p-6"
        noValidate
      >
        <Field label="Tiêu đề" htmlFor="title" required error={errors.title?.message}>
          <input
            id="title"
            {...register('title')}
            className={inputClass}
            placeholder="Ví dụ: Không kết nối được WiFi công ty tại tầng 5"
            aria-invalid={Boolean(errors.title)}
          />
        </Field>

        <Field
          label="Mô tả chi tiết"
          htmlFor="description"
          required
          error={errors.description?.message}
          hint={`Sự cố xảy ra từ khi nào, bạn đã thử cách nào rồi? (${description.length}/5000)`}
        >
          <textarea
            id="description"
            rows={6}
            {...register('description')}
            className={inputClass}
            placeholder="Từ sáng nay máy tôi không thấy mạng CTY-WIFI trong danh sách…"
            aria-invalid={Boolean(errors.description)}
          />
        </Field>

        <Field
          label="Mức độ ưu tiên"
          htmlFor="priority"
          hint="Để trống thì hệ thống tự đánh giá theo loại sự cố."
        >
          <select id="priority" {...register('priority')} className={inputClass}>
            <option value="">Để hệ thống tự đánh giá</option>
            {PRIORITY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </Field>

        <div className="mt-6 flex gap-3">
          <Button type="submit" loading={createTicket.isPending}>
            Gửi yêu cầu
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate(-1)}>
            Huỷ
          </Button>
        </div>
      </form>
    </div>
  )
}
