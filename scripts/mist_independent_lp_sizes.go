// Read-only independent comparison using pinned third-party lpunpack-go parser.
// Compile alongside its pinned super.go: go run independent_check.go super.go --image-path
package main

import (
  "encoding/json"
  "fmt"
  "os"
)
func main() {
  if len(os.Args)!=2 { fmt.Fprintln(os.Stderr,"usage: lp-size-check IMAGE"); os.Exit(2) }
  sp,err:=OpenSuperImage(os.Args[1],false)
  if err!=nil { panic(err) }
  defer sp.Close()
  result:=make(map[string]uint64)
  for _,p:=range sp.Partitions {
    if _,exists:=result[p.Name];exists { panic("duplicate partition: "+p.Name) }
    result[p.Name]=p.Size
  }
  if err:=json.NewEncoder(os.Stdout).Encode(result);err!=nil {panic(err)}
}
