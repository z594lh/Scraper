import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Input,
  message,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd'
import { SaveOutlined, SendOutlined } from '@ant-design/icons'
import { api } from '../api'
import type { NotifySettings, SystemInfo } from '../types'

export default function Settings() {
  const [messageApi, contextHolder] = message.useMessage()
  const [settings, setSettings] = useState<NotifySettings | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [notifyEnabled, setNotifyEnabled] = useState(true)
  const [dingtalk, setDingtalk] = useState('')
  const [secret, setSecret] = useState('')
  const [wecom, setWecom] = useState('')
  const [chrome, setChrome] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState('')

  const load = async () => {
    const [s, sys] = await Promise.all([api.settings(), api.system()])
    setSettings(s)
    setSystem(sys)
    setNotifyEnabled(s.notifyEnabled)
    setChrome(s.pzdsChrome)
    setDingtalk('')
    setSecret('')
    setWecom('')
  }

  useEffect(() => {
    load().catch((error) => messageApi.error((error as Error).message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        notifyEnabled,
        pzdsChrome: chrome,
      }
      if (dingtalk.trim()) body.dingtalkWebhook = dingtalk.trim()
      if (secret.trim()) body.dingtalkSecret = secret.trim()
      if (wecom.trim()) body.wecomWebhook = wecom.trim()
      const saved = await api.saveSettings(body)
      setSettings(saved)
      setDingtalk('')
      setSecret('')
      setWecom('')
      messageApi.success('已保存到 .env')
    } catch (error) {
      messageApi.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const test = async (channel: string) => {
    setTesting(channel)
    try {
      await api.testNotify(channel)
      messageApi.success('测试消息已发送，请查看客户端')
    } catch (error) {
      messageApi.error((error as Error).message)
    } finally {
      setTesting('')
    }
  }

  return (
    <div>
      {contextHolder}
      <h1 className="page-title">通知与系统</h1>
      <div className="page-sub">
        敏感信息保存在仓库根目录的 .env（已加入 .gitignore），接口只返回脱敏值。
      </div>

      <Row gutter={16}>
        <Col xs={24} xl={14}>
          <Card title="通知渠道" style={{ marginBottom: 16 }}>
            <Space style={{ marginBottom: 16 }}>
              <Switch checked={notifyEnabled} onChange={setNotifyEnabled} />
              <span>启用通知</span>
              {!notifyEnabled && <Tag>已关闭</Tag>}
            </Space>
            <Divider style={{ margin: '8px 0 16px' }} />

            <Typography.Title level={5} style={{ marginTop: 0 }}>
              钉钉机器人
              {settings?.dingtalk.configured ? (
                <Tag color="green" style={{ marginLeft: 8 }}>
                  已配置 {settings.dingtalk.masked}
                </Tag>
              ) : (
                <Tag style={{ marginLeft: 8 }}>未配置</Tag>
              )}
            </Typography.Title>
            <div className="muted" style={{ marginBottom: 6 }}>
              Webhook 地址（留空表示不修改）
            </div>
            <Input.Password
              value={dingtalk}
              onChange={(e) => setDingtalk(e.target.value)}
              placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
              style={{ marginBottom: 12 }}
            />
            <div className="muted" style={{ marginBottom: 6 }}>
              加签密钥（可选，留空表示不修改）
            </div>
            <Input.Password
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder={settings?.dingtalkSecret.configured ? `已配置 ${settings.dingtalkSecret.masked}` : 'SEC...'}
              style={{ marginBottom: 12 }}
            />
            <Button
              icon={<SendOutlined />}
              loading={testing === 'dingtalk'}
              onClick={() => test('dingtalk')}
            >
              发送测试消息
            </Button>

            <Divider />

            <Typography.Title level={5} style={{ marginTop: 0 }}>
              企业微信群机器人
              {settings?.wecom.configured ? (
                <Tag color="green" style={{ marginLeft: 8 }}>
                  已配置 {settings.wecom.masked}
                </Tag>
              ) : (
                <Tag style={{ marginLeft: 8 }}>未配置</Tag>
              )}
            </Typography.Title>
            <div className="muted" style={{ marginBottom: 6 }}>
              Webhook 地址（留空表示不修改）
            </div>
            <Input.Password
              value={wecom}
              onChange={(e) => setWecom(e.target.value)}
              placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
              style={{ marginBottom: 12 }}
            />
            <Button icon={<SendOutlined />} loading={testing === 'wecom'} onClick={() => test('wecom')}>
              发送测试消息
            </Button>

            <Divider />
            <Typography.Title level={5} style={{ marginTop: 0 }}>
              浏览器
            </Typography.Title>
            <div className="muted" style={{ marginBottom: 6 }}>
              Chrome 可执行文件路径（虚拟机请填 /usr/bin/google-chrome；本机留空）
            </div>
            <Input
              value={chrome}
              onChange={(e) => setChrome(e.target.value)}
              placeholder="留空则使用本机 Chrome 通道"
            />

            <div style={{ marginTop: 20 }}>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
                保存设置
              </Button>
              <span className="muted" style={{ marginLeft: 12 }}>
                保存后再发送测试消息才会使用新配置
              </span>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card title="运行环境">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Python">{system?.python ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="系统">{system?.platform ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="仓库根目录">{system?.root ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="数据库">{system?.database ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="项目指纹目录">{system?.projectsDir ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="浏览器">{system?.chrome ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="环境文件">{system?.envFile ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="定时调度">
                {settings?.schedulerEnabled ? <Tag color="green">已启用</Tag> : <Tag>已关闭</Tag>}
              </Descriptions.Item>
            </Descriptions>
            <Divider style={{ margin: '12px 0' }} />
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0 }}>
              每个项目拥有独立的浏览器指纹目录，登录态互不影响。新增数据源（如螃蟹账号）时，
              在后端 crawlers 目录实现一个新类并注册即可，配置页会自动沿用同一套项目结构。
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
