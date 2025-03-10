import {
  ListResourceOrganization,
  Organization,
  OrganizationBadgeSettingsUpdate,
  OrganizationUpdate,
  Platforms,
} from '@polar-sh/sdk'
import {
  UseMutationResult,
  UseQueryResult,
  useMutation,
  useQuery,
} from '@tanstack/react-query'
import { api, queryClient } from '../../api'
import { defaultRetry, serverErrorRetry } from './retry'

export const useListAdminOrganizations: () => UseQueryResult<ListResourceOrganization> =
  () =>
    useQuery({
      queryKey: ['user', 'adminOrganizations'],
      queryFn: () =>
        api.organizations.list({
          isAdminOnly: true,
        }),
      retry: defaultRetry,
    })

export const useOrganizationLookup: (
  name: string,
  platform?: Platforms,
) => UseQueryResult<Organization> = (name, platform = Platforms.GITHUB) =>
  useQuery({
    queryKey: ['organizations', name],
    queryFn: () =>
      api.organizations.lookup({ organizationName: name, platform }),
    retry: defaultRetry,
  })

export const useListAllOrganizations = (isAdminOnly = false) =>
  useQuery({
    queryKey: ['user', 'allOrganizations', isAdminOnly],
    queryFn: () =>
      api.organizations.list({
        isAdminOnly,
      }),
    retry: defaultRetry,
  })

export const useListOrganizationMembers = (id?: string) =>
  useQuery({
    queryKey: ['organizationMembers', id],
    queryFn: () =>
      api.organizations.listMembers({
        id: id || '',
      }),
    retry: defaultRetry,
    enabled: !!id,
  })

export const useSyncOrganizationMembers = () =>
  useMutation({
    mutationFn: (variables: { id: string }) =>
      api.integrations.synchronizeMembers({
        organizationId: variables.id,
      }),
    retry: defaultRetry,
    onSuccess: (result, variables, ctx) => {
      queryClient.invalidateQueries({
        queryKey: ['organizationMembers', variables.id],
      })
      queryClient.invalidateQueries({
        queryKey: ['user', 'adminOrganizations'],
      })
      queryClient.invalidateQueries({
        queryKey: ['user', 'allOrganizations'],
      })
    },
  })

export const useOrganizationBadgeSettings = (id: string) =>
  useQuery({
    queryKey: ['organizationBadgeSettings', id],
    queryFn: () => api.organizations.getBadgeSettings({ id }),
    retry: defaultRetry,
  })

export const useUpdateOrganizationBadgeSettings: () => UseMutationResult<
  Organization,
  Error,
  {
    id: string
    settings: OrganizationBadgeSettingsUpdate
  },
  unknown
> = () =>
  useMutation({
    mutationFn: (variables: {
      id: string
      settings: OrganizationBadgeSettingsUpdate
    }) => {
      return api.organizations.updateBadgeSettings({
        id: variables.id,
        organizationBadgeSettingsUpdate: variables.settings,
      })
    },
    onSuccess: (result, variables, ctx) => {
      queryClient.invalidateQueries({
        queryKey: ['organizationBadgeSettings', variables.id],
      })
    },
  })

const updateOrgsCache = (result: Organization) => {
  queryClient.setQueriesData<ListResourceOrganization>(
    {
      queryKey: ['user', 'adminOrganizations'],
    },
    (data) => {
      if (!data) {
        return data
      }

      return {
        ...data,
        items: data.items?.map((i) => {
          if (i.id === result.id) {
            return {
              ...i,
              issue: result,
            }
          }
          return { ...i }
        }),
      }
    },
  )

  queryClient.setQueriesData<ListResourceOrganization>(
    {
      queryKey: ['user', 'allOrganizations'],
    },
    (data) => {
      if (!data) {
        return data
      }

      return {
        ...data,
        items: data.items?.map((i) => {
          if (i.id === result.id) {
            return {
              ...i,
              issue: result,
            }
          }
          return { ...i }
        }),
      }
    },
  )
}

export const useUpdateOrganization = () =>
  useMutation({
    mutationFn: (variables: { id: string; settings: OrganizationUpdate }) => {
      return api.organizations.update({
        id: variables.id,
        organizationUpdate: variables.settings,
      })
    },
    onSuccess: (result, variables, ctx) => {
      updateOrgsCache(result)
    },
  })

export const useOrganizationCredits = (id?: string) =>
  useQuery({
    queryKey: ['organizationCredits', id],
    queryFn: () => api.organizations.getCredits({ id: id || '' }),
    retry: serverErrorRetry,
    enabled: !!id,
  })

export const useOrganization = (id: string) =>
  useQuery({
    queryKey: ['organization', id],
    queryFn: () => api.organizations.get({ id }),
    retry: defaultRetry,
    enabled: !!id,
  })
