import { Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import type { ItemRow, SiteColumn } from '../types'

interface Props {
  columns: SiteColumn[]
  items: ItemRow[]
  loading?: boolean
}

function renderValue(column: SiteColumn, value: unknown, row: ItemRow) {
  switch (column.type) {
    case 'code':
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Typography.Text copyable={{ text: String(value ?? '') }}>{String(value ?? '')}</Typography.Text>
          {row.isNew ? <Tag color="green">NEW</Tag> : null}
        </span>
      )
    case 'price':
      return value == null ? <span className="muted">-</span> : <span className="price">¥{Number(value).toLocaleString()}</span>
    case 'tags': {
      const tags = Array.isArray(value) ? (value as string[]) : []
      if (!tags.length) return <span className="muted">-</span>
      const head = tags.slice(0, 2)
      return (
        <span>
          {head.map((tag) => (
            <Tag key={tag} color="geekblue" style={{ marginBottom: 2 }}>
              {tag}
            </Tag>
          ))}
          {tags.length > head.length ? (
            <Tooltip title={tags.slice(head.length).join(' / ')}>
              <Tag>+{tags.length - head.length}</Tag>
            </Tooltip>
          ) : null}
        </span>
      )
    }
    case 'datetime':
      return value ? <span className="muted">{dayjs(String(value)).format('MM-DD HH:mm')}</span> : <span className="muted">-</span>
    case 'link':
      return value ? (
        <a href={String(value)} target="_blank" rel="noreferrer">
          详情
        </a>
      ) : (
        <span className="muted">-</span>
      )
    default:
      return column.ellipsis ? (
        <Tooltip title={String(value ?? '')}>
          <span className="item-title">{String(value ?? '')}</span>
        </Tooltip>
      ) : (
        String(value ?? '')
      )
  }
}

export default function ItemsTable({ columns, items, loading }: Props) {
  const antdColumns: ColumnsType<ItemRow> = columns.map((column) => ({
    title: column.title,
    dataIndex: column.key,
    key: column.key,
    width: column.width,
    ellipsis: column.ellipsis,
    sorter: column.sortable
      ? (a, b) => Number(a[column.key] ?? 0) - Number(b[column.key] ?? 0)
      : undefined,
    render: (value: unknown, row: ItemRow) => renderValue(column, value, row),
  }))

  return (
    <Table
      size="small"
      rowKey="goodsNo"
      loading={loading}
      columns={antdColumns}
      dataSource={items}
      scroll={{ x: 'max-content' }}
      pagination={{ pageSize: 20, showSizeChanger: false, hideOnSinglePage: true }}
    />
  )
}
