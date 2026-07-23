{{- define "visits.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "visits.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "visits.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "visits.labels" -}}
app.kubernetes.io/name: {{ include "visits.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}
