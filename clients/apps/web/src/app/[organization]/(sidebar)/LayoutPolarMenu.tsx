'use client'

import PublicProfileDropdown from '@/components/Navigation/PublicProfileDropdown'
import { useAuth, useCurrentOrgAndRepoFromURL } from '@/hooks'
import { ArrowForwardOutlined } from '@mui/icons-material'
import { Organization, UserRead } from '@polar-sh/sdk'
import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
import { getGitHubAuthorizeURL } from 'polarkit/auth'
import Button from 'polarkit/components/ui/atoms/button'
import { CONFIG } from 'polarkit/config'

export const PolarMenu = ({
  authenticatedUser,
  userAdminOrganizations,
  organization,
}: {
  authenticatedUser?: UserRead
  userAdminOrganizations: Organization[]
  organization: Organization
}) => {
  const pathname = usePathname()
  const returnTo = pathname ?? '/feed'

  // Fallback to client side user loading (needed as we're loading data in the layout, and it isn't refreshed on navigation)
  const { currentUser: clientCurrentUser } = useAuth()
  const currentUser = authenticatedUser ?? clientCurrentUser

  // Fallback to client side org loading
  const { org: clientOrg } = useCurrentOrgAndRepoFromURL()
  const currentOrg = clientOrg ?? organization

  const personalOrg = userAdminOrganizations?.find((o) => o.is_personal)

  const hasAdminOrgs = Boolean(
    userAdminOrganizations && userAdminOrganizations.length > 0,
  )

  const creatorPath = personalOrg
    ? `${CONFIG.FRONTEND_BASE_URL}/maintainer/${currentUser?.username}/overview`
    : `${CONFIG.FRONTEND_BASE_URL}/maintainer/${userAdminOrganizations?.[0]?.name}/overview`

  // Login through polar.sh with auth forwarding if on custom domain
  const loginLink = currentOrg.custom_domain
    ? `${CONFIG.FRONTEND_BASE_URL}/login?return_to=${returnTo}&for_organization_id=${currentOrg.id}`
    : `${CONFIG.FRONTEND_BASE_URL}/login?return_to=${returnTo}`

  return (
    <div className="flex flex-row items-center gap-x-4">
      {authenticatedUser ? (
        <div>
          <div className="relative flex w-max flex-shrink-0 flex-row items-center justify-between gap-x-6">
            {hasAdminOrgs && (
              <Link href={creatorPath}>
                <Button>
                  <div className="flex flex-row items-center gap-x-2">
                    <span className="whitespace-nowrap text-xs">
                      Creator Dashboard
                    </span>
                    <ArrowForwardOutlined fontSize="inherit" />
                  </div>
                </Button>
              </Link>
            )}
            <PublicProfileDropdown
              authenticatedUser={authenticatedUser}
              className="flex-shrink-0"
              allBackerRoutes
            />
          </div>
        </div>
      ) : (
        <>
          <CreateWithPolar returnTo={returnTo} />
          <Link
            href={loginLink}
            className="text-sm text-blue-500 hover:text-blue-400 dark:text-blue-400 dark:hover:text-blue-300"
          >
            Login
          </Link>
        </>
      )}
    </div>
  )
}

const CreateWithPolar = ({ returnTo }: { returnTo: string }) => {
  const search = useSearchParams()
  const authorizeURL = getGitHubAuthorizeURL({
    paymentIntentId: search?.get('payment_intent_id') ?? undefined,
    returnTo: returnTo,
  })

  return (
    <a href={authorizeURL}>
      <Button variant="secondary" asChild>
        Create with Polar
      </Button>
    </a>
  )
}
