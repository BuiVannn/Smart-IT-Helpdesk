# Custom hooks

Quy ước `queryKey` của TanStack Query — phân cấp để invalidate đúng phạm vi:

```
['tickets']             → toàn bộ danh sách ticket
['tickets', filters]    → danh sách theo bộ lọc cụ thể
['tickets', id]         → một ticket
['notifications']       → thông báo
['reports', name, args] → báo cáo
```

Sau mutation LUÔN dùng `invalidateQueries`, KHÔNG tự sửa cache bằng tay
(dễ lệch với server).

Polling chỉ chạy khi tab đang hiển thị:
```ts
refetchInterval: () => document.visibilityState === 'visible' ? 20_000 : false
```
