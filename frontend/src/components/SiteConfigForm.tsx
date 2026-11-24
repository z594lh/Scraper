import { Col, Input, InputNumber, Row, Select, Switch, Tooltip } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import type { ConfigField, ConfigGroup } from '../types'

interface Props {
  schema: ConfigGroup[]
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  /** 抓取时同步的站点枚举：{ 分组名: [选项...] } */
  options?: Record<string, string[]>
}

function TagsEditor({
  groups,
  optionMap,
  onChange,
}: {
  groups: Record<string, string[]>
  optionMap: Record<string, string[]>
  onChange: (groups: Record<string, string[]>) => void
}) {
  const entries = Object.entries(groups ?? {})
  const update = (index: number, label: string, tags: string[]) => {
    const next: Record<string, string[]> = {}
    entries.forEach(([oldLabel, oldTags], i) => {
      const key = i === index ? label || oldLabel : oldLabel
      next[key] = i === index ? tags : oldTags
    })
    onChange(next)
  }
  return (
    <div>
      {entries.map(([label, tags], index) => (
        <div className="tag-editor-group" key={`${label}-${index}`}>
          <Row gutter={8} align="middle">
            <Col span={8}>
              <Input
                value={label}
                placeholder="分组名，如 珍品外观"
                onChange={(event) => update(index, event.target.value, tags)}
              />
            </Col>
            <Col span={14}>
              <Select
                mode="tags"
                style={{ width: '100%' }}
                value={tags}
                placeholder="从下拉选择，或输入新标签后回车"
                options={(optionMap[label] ?? []).map((item) => ({ label: item, value: item }))}
                onChange={(next) => update(index, label, next)}
              />
            </Col>
            <Col span={2}>
              <Tooltip title="删除该分组">
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => {
                    const next = { ...groups }
                    delete next[label]
                    onChange(next)
                  }}
                />
              </Tooltip>
            </Col>
          </Row>
        </div>
      ))}
      <Button
        icon={<PlusOutlined />}
        onClick={() => onChange({ ...groups, [`分组${entries.length + 1}`]: [] })}
      >
        新增分组
      </Button>
    </div>
  )
}

export default function SiteConfigForm({ schema, value, onChange, options }: Props) {
  const set = (key: string, next: unknown) => onChange({ ...value, [key]: next })

  const renderField = (field: ConfigField) => {
    const current = value[field.key]
    switch (field.type) {
      case 'number':
        return (
          <InputNumber
            style={{ width: '100%' }}
            value={typeof current === 'number' ? current : undefined}
            placeholder={field.placeholder}
            onChange={(next) => set(field.key, next ?? 0)}
          />
        )
      case 'switch':
        return <Switch checked={Boolean(current)} onChange={(next) => set(field.key, next)} />
      case 'range': {
        const range = Array.isArray(current) ? (current as number[]) : [8, 11]
        return (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <InputNumber
              value={range[0]}
              min={0}
              onChange={(next) => set(field.key, [next ?? 0, range[1]])}
            />
            <span className="muted">至</span>
            <InputNumber
              value={range[1]}
              min={0}
              onChange={(next) => set(field.key, [range[0], next ?? 0])}
            />
            <span className="muted">秒</span>
          </div>
        )
      }
      case 'select':
        return (
          <Select
            style={{ width: '100%' }}
            value={current as string | number | undefined}
            options={field.options}
            onChange={(next) => set(field.key, next)}
          />
        )
      case 'tags':
        return (
          <TagsEditor
            groups={(current as Record<string, string[]>) ?? {}}
            optionMap={options ?? {}}
            onChange={(next) => set(field.key, next)}
          />
        )
      default:
        return (
          <Input
            value={(current as string) ?? ''}
            placeholder={field.placeholder}
            onChange={(event) => set(field.key, event.target.value)}
          />
        )
    }
  }

  return (
    <>
      {schema.map((group) => (
        <div className="config-group" key={group.group}>
          <div className="config-group-title">{group.group}</div>
          <Row gutter={[16, 4]}>
            {group.items.map((field) => (
              <Col xs={24} md={field.type === 'tags' ? 24 : 12} key={field.key}>
                <div className="field">
                  <div className="field-label">
                    {field.label}
                    {field.required ? <span className="required"> *</span> : null}
                  </div>
                  {renderField(field)}
                  {field.help ? <div className="muted" style={{ marginTop: 4 }}>{field.help}</div> : null}
                </div>
              </Col>
            ))}
          </Row>
        </div>
      ))}
    </>
  )
}
