import { redirect } from 'next/navigation'

interface LegacyResearchPageProps {
  params: {
    runId: string
  }
}

export default function LegacyResearchPage({ params }: LegacyResearchPageProps) {
  redirect(`/combo-reports/${params.runId}`)
}
