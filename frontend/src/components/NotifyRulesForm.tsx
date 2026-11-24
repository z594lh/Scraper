import { Col, InputNumber, Row, Space, Switch } from 'antd'
import type { NotifyRules } from '../types'

interface Props {
  value: NotifyRules
  onChange: (next: NotifyRules) => void
}

/** 通知规则：新增条数阈值 / 执行失败 / 每次执行完成。 */
export default function NotifyRulesForm({ value, onChange }: Props) {
  const setNew = (patch: Partial<NotifyRules['newItems']>) =>
    onChange({ ...value, newItems: { ...value.newItems, ...patch } })

  return (
    <div className="config-group">
      <div className="config-group-title">通知规则</div>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <div className="field">
            <div className="field-label">新增数据提醒</div>
            <Space wrap>
              <Switch
                checked={value.newItems.enabled}
                onChange={(next) => setNew({ enabled: next })}
              />
              <span className="muted">新增达到</span>
              <InputNumber
                min={1}
                max={999}
                value={value.newItems.threshold}
                disabled={!value.newItems.enabled}
                onChange={(next) => setNew({ threshold: next ?? 1 })}
                style={{ width: 80 }}
              />
              <span className="muted">条时通知</span>
            </Space>
            <div className="muted" style={{ marginTop: 4 }}>
              首次运行只建立基线，不会触发新增提醒
            </div>
          </div>
        </Col>
        <Col xs={24} md={12}>
          <div className="field">
            <div className="field-label">执行失败提醒</div>
            <Switch
              checked={value.runFailed.enabled}
              onChange={(next) => onChange({ ...value, runFailed: { enabled: next } })}
            />
            <div className="muted" style={{ marginTop: 4 }}>
              登录态失效、被滑块拦截、抓取异常时通知
            </div>
          </div>
        </Col>
        <Col xs={24} md={12}>
          <div className="field">
            <div className="field-label">每次执行完成通知</div>
            <Switch
              checked={value.runFinished.enabled}
              onChange={(next) => onChange({ ...value, runFinished: { enabled: next } })}
            />
            <div className="muted" style={{ marginTop: 4 }}>
              不论有无新增，每次抓取结束都发送汇总（抓取数/新增数）
            </div>
          </div>
        </Col>
      </Row>
    </div>
  )
}
